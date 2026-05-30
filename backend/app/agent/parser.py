import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..logging_config import get_logger
from .schemas import CALENDAR_INTENT, SMALLTALK_INTENT, UNCLEAR_INTENT, ActionPlan

logger = get_logger("agent.parser")


def classify_intent(text: str, timezone: str) -> ActionPlan:
    normalized_text = text.strip()
    logger.info("intent_classify_start text_length=%s timezone=%s", len(normalized_text), timezone)

    if not normalized_text:
        logger.warning("intent_classify_unclear reason=empty_text")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我没有听清楚。你可以试试说：“明天下午三点开会”。")

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.error("intent_classify_failed reason=missing_api_key")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="当前没有配置可用的 Agent 模型 API Key，暂时无法理解指令。")

    try:
        payload = _invoke_json(
            _intent_prompt(),
            {
                "text": normalized_text,
                "timezone": timezone,
                "current_datetime": _current_datetime(timezone),
            },
        )
    except Exception:
        logger.exception("intent_classify_failed reason=llm_error")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我暂时没能理解这句话，请再说一次日程需求。")
    plan = ActionPlan.from_dict(
        {
            "intent": payload.get("intent"),
            "reply": payload.get("reply"),
            "actions": [],
        }
    )
    logger.info("intent_classify_success intent=%s reply=%s", plan.intent, plan.reply)

    return plan


def plan_calendar_actions(text: str, timezone: str) -> ActionPlan:
    normalized_text = text.strip()
    logger.info("action_plan_start text_length=%s timezone=%s", len(normalized_text), timezone)

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.error("action_plan_failed reason=missing_api_key")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="当前没有配置可用的 Agent 模型 API Key，暂时无法提取日程任务。")

    try:
        payload = _invoke_json(
            _planner_prompt(),
            {
                "text": normalized_text,
                "timezone": timezone,
                "current_datetime": _current_datetime(timezone),
            },
        )
    except Exception:
        logger.exception("action_plan_failed reason=llm_error")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我暂时没能提取出日程任务，请换一种说法再试一次。")
    plan = ActionPlan.from_dict(
        {
            "intent": CALENDAR_INTENT,
            "reply": payload.get("reply"),
            "actions": payload.get("actions") or [],
        }
    )
    logger.info(
        "action_plan_success action_count=%s actions=%s",
        len(plan.actions),
        [action.to_dict() for action in plan.actions],
    )

    return plan


def generate_smalltalk_reply(text: str, timezone: str) -> str:
    normalized_text = text.strip()
    logger.info("smalltalk_reply_start text_length=%s timezone=%s", len(normalized_text), timezone)

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.error("smalltalk_reply_failed reason=missing_api_key")
        return "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。"

    try:
        payload = _invoke_json(
            _smalltalk_prompt(),
            {
                "text": normalized_text,
                "timezone": timezone,
                "current_datetime": _current_datetime(timezone),
            },
        )
    except Exception:
        logger.exception("smalltalk_reply_failed reason=llm_error")
        return "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。"
    reply = str(payload.get("reply") or "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。").strip()
    logger.info("smalltalk_reply_success reply_length=%s", len(reply))

    return reply


def parse_command(text: str, timezone: str) -> ActionPlan:
    intent_plan = classify_intent(text, timezone)

    if intent_plan.intent != CALENDAR_INTENT:
        return intent_plan

    return plan_calendar_actions(text, timezone)


def _invoke_json(system_prompt: str, payload: dict) -> dict:
    model = ChatOpenAI(
        model=current_app.config["AGENT_MODEL"],
        temperature=current_app.config["AGENT_TEMPERATURE"],
        api_key=current_app.config["OPENAI_API_KEY"],
        base_url=current_app.config["OPENAI_BASE_URL"],
    )
    response = model.bind(response_format={"type": "json_object"}).invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
        ]
    )

    return json.loads(response.content)


def _current_datetime(timezone: str) -> str:
    return datetime.now(ZoneInfo(timezone)).isoformat()


def _intent_prompt() -> str:
    return """
You are the intent recognition node for a voice calendar assistant. Return JSON only.

Schema:
{
  "intent": "calendar" | "smalltalk" | "unsupported" | "unclear",
  "reply": string | null
}

Definitions:
- calendar: the user wants to create, delete, update, query, list, clear, cancel, or reschedule calendar events/reminders. A single utterance may contain multiple calendar tasks.
- smalltalk: greetings, thanks, casual chat, or non-task conversation that can be answered briefly.
- unsupported: a clear request outside calendar capability, such as weather, email, maps, news, coding, shopping.
- unclear: too short, incomplete, ambiguous, or not enough information to infer intent.

Rules:
- Only classify intent; do not extract tasks here.
- For smalltalk or unsupported, provide a concise Chinese reply and gently guide the user to calendar usage.
- For calendar, set reply to null.
""".strip()


def _planner_prompt() -> str:
    return """
You are the task extraction node for a voice calendar assistant. Return JSON only.

Schema:
{
  "reply": string | null,
  "actions": [
    {
      "type": "create_event" | "query_events" | "update_event" | "delete_event",
      "confidence": number,
      "arguments": object
    }
  ]
}

Action argument rules:
- create_event arguments: title, start_time, end_time, notes, recurrence_type, recurrence_interval, recurrence_until.
- query_events arguments: date or start/end, plus optional keywords.
- update_event arguments: selector and updates.
- delete_event arguments: selector.
- selector may include date, start, end, keywords, and all.
- recurrence_type must be one of none, daily, weekly, monthly.
- recurrence_interval defaults to 1.
- Use ISO datetime strings with the provided timezone.
- If end_time is not stated for create/update, set it to one hour after start_time.
- If the user says every day/week/month, set recurrence_type accordingly.
- If the user clearly asks to delete all events on a day, set selector.all to true and do not add keywords.
- For deleting/updating a single named event, include date/time when stated and include meaningful keywords from the event title/person/place.
- Preserve all names, people, companies, places, event nouns, possible typos, and user-specific wording.

Multi-task rules:
- Always return actions as a list.
- If the user asks for multiple operations in one sentence, return one action per operation in original order.
- Do not merge multiple event creations/deletions/updates into one action.
- Extract create, delete, update, and query operations from the same utterance when present.
- If a later task omits the date but the utterance already established one, inherit that date.
- If a later task omits 上午/下午/晚上 but context implies it, infer reasonably from the surrounding phrase.

Examples:
Input text: 明天上午9点开产品讨论会，10点半有一个面试，然后晚上跟李总的晚饭取消
Output actions:
- create_event 产品讨论会 at tomorrow 09:00
- create_event 面试 at tomorrow 10:30
- delete_event selector date tomorrow keywords ["李总", "晚饭"]

Input text: 删除明天所有日程
Output actions:
- delete_event selector date tomorrow all true keywords []

Rules:
- Do not execute anything. Only plan.
- If no executable calendar action can be extracted, return an empty actions list and a short Chinese reply.
""".strip()


def _smalltalk_prompt() -> str:
    return """
You are the chat response node for a voice calendar assistant. Return JSON only.

Schema:
{
  "reply": string
}

Rules:
- Reply in concise, friendly Chinese.
- If the user is casually chatting, answer briefly.
- Gently guide the user toward calendar commands when helpful.
- Do not claim that you executed calendar operations.
""".strip()
