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
        return ActionPlan(intent=UNCLEAR_INTENT, reply="你说话了吗？我没听见，再说一遍吧。")

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.error("intent_classify_failed reason=missing_api_key")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="日程助手还没有配置好，暂时不能理解语音或文字指令。")

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
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我刚才没理解清楚，请换个说法再说一次日程需求。")
    plan = ActionPlan.from_dict(
        {
            "intent": payload.get("intent"),
            "reply": payload.get("reply"),
            "actions": [],
        }
    )
    logger.info("intent_classify_success intent=%s reply=%s", plan.intent, plan.reply)

    return plan


def plan_calendar_actions(
    text: str,
    timezone: str,
    existing_events: list[dict] | None = None,
    recent_events: list[dict] | None = None,
    recent_turns: list[dict] | None = None,
) -> ActionPlan:
    normalized_text = text.strip()
    logger.info("action_plan_start text_length=%s timezone=%s", len(normalized_text), timezone)

    if not current_app.config.get("OPENAI_API_KEY"):
        logger.error("action_plan_failed reason=missing_api_key")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="日程助手还没有配置好，暂时不能提取日程任务。")

    try:
        payload = _invoke_json(
            _planner_prompt(),
            {
                "text": normalized_text,
                "timezone": timezone,
                "current_datetime": _current_datetime(timezone),
                "existing_events": _planner_event_context(existing_events or []),
                "recent_events": _planner_event_context(recent_events or []),
                "recent_turns": _planner_turn_context(recent_turns or []),
            },
        )
    except Exception:
        logger.exception("action_plan_failed reason=llm_error")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我没能提取出具体日程，请说清楚时间和要做的事。")
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


def _planner_event_context(events: list[dict], limit: int = 30) -> list[dict]:
    context = []

    for event in events[:limit]:
        context.append(
            {
                "id": event.get("series_id") or event.get("id"),
                "title": event.get("title"),
                "start_time": event.get("start_time"),
                "end_time": event.get("end_time"),
            }
        )

    return context


def _planner_turn_context(turns: list[dict], limit: int = 5) -> list[dict]:
    context = []

    for turn in turns[:limit]:
        context.append(
            {
                "user_text": turn.get("user_text"),
                "assistant_message": turn.get("assistant_message"),
                "status": turn.get("status"),
                "intent": turn.get("intent"),
                "actions": turn.get("actions", []),
                "events": _planner_event_context(turn.get("events", []), limit=8),
            }
        )

    return context


def _intent_prompt() -> str:
    return """
你是语音日历助手的“意图识别”节点。你只能返回 JSON，不要输出解释文字。

输出结构：
{
  "intent": "calendar" | "smalltalk" | "unsupported" | "unclear",
  "reply": string | null
}

意图定义：
- calendar：用户想创建、删除、修改、查询、列出、清空、取消或改期日程/提醒。一句话里可能包含多个日程任务。
- smalltalk：问候、感谢、闲聊，或不需要执行任务的普通对话。
- unsupported：明确超出日历能力范围的请求，例如天气、邮件、地图、新闻、编程、购物等。
- unclear：文本太短、不完整、含糊，或没有足够信息判断用户意图。

规则：
- 这里只做意图识别，不要提取具体任务。
- 如果是 smalltalk 或 unsupported，给出简短中文回复，并自然引导用户使用日历功能。
- 如果是 calendar，reply 必须为 null。
""".strip()


def _planner_prompt() -> str:
    return """
你是语音日历助手的“任务提取”节点。你只能返回 JSON，不要输出解释文字。

输出结构：
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

动作参数规则：
- create_event 的 arguments 使用：title、start_time、end_time、notes、recurrence_type、recurrence_interval、recurrence_until。
- query_events 的 arguments 使用：date 或 start/end，可附加 keywords。
- update_event 的 arguments 使用：selector 和 updates。
- delete_event 的 arguments 使用：selector。
- selector 可包含：date、start、end、keywords、all。
- recurrence_type 只能是：none、daily、weekly、monthly。
- recurrence_interval 默认是 1。
- 时间必须使用带有用户 timezone 的 ISO datetime 字符串。
- 创建或修改事件时，如果用户没有说明 end_time，则设为 start_time 后一小时。
- 如果用户说每天、每周、每月，按语义设置 recurrence_type。
- 如果用户明确要求删除某天所有事件，设置 selector.all 为 true，keywords 设为空数组。
- 如果是删除/修改单个具名事件，用户提到日期或时间时要放入 selector，并从事件标题、人名、地点中提取有意义的 keywords。
- 必须保留所有人名、公司名、地点、事件名、专有名词、可能的错别字，以及用户自己的表达。
- 输入 JSON 里会提供 existing_events，表示用户近期已有日程，可用于判断用户是在修改已有日程。
- 输入 JSON 里会提供 recent_events，表示当前对话里刚刚创建、修改或查询过的日程，按从新到旧排序。它是短期记忆，优先级高于 existing_events。
- 输入 JSON 里会提供 recent_turns，表示当前会话最近几轮用户原话、助手回复、动作和涉及日程。它用于理解跨轮省略、纠正和指代。
- 当用户说“X 是 Y”、“X 改成 Y”、“把 X 改为 Y”、“X 其实是 Y”、“X 不是 A 是 B”这类纠正或补充时，如果 existing_events 中有标题能被 X 匹配的日程，必须输出 update_event，不要输出 create_event。
- 这类 update_event 的 selector.keywords 使用原日程关键词 X；如果 existing_events 里匹配到该日程，selector 也应带上它的日期或 start/end，updates.title 使用修改后的完整新标题 Y。
- 不要为了“考试是雅思考试”“安装的家具是电动升降桌”这类表达创建同时间的新日程；应把已有“考试”改为“考雅思”或“雅思考试”，把已有“安装家具”改为“安装电动升降桌”。
- 当用户说“刚刚说的”、“刚才那个”、“刚添加的”、“上一个”、“这个”、“那个”等指代时，必须优先从 recent_events 里选择被指代日程。
- 如果 recent_events 不够明确，结合 recent_turns 里最近用户说过的对象、动作和事件来判断指代对象。
- 如果 recent_events 里能确定唯一指代对象，update_event/delete_event 的 selector 必须使用 event_id 精确指向该日程，不要只用模糊 keywords。
- 例如用户刚刚创建了 recent_events[0] = {"id": 4, "title": "会议4"}，随后说“把我刚刚说的会议时间改到3点”，应输出 update_event，selector.event_id 为 4，updates.start_time 改为今天 15:00，并相应调整 end_time。

多任务规则：
- actions 必须始终是数组。
- 如果一句话里有多个操作，按用户原始顺序为每个操作返回一个 action。
- 不要把多个创建、删除、修改任务合并成一个 action。
- 同一句话里可以同时提取创建、删除、修改、查询任务。
- 如果后面的任务省略日期，但前文已经给出日期，需要继承该日期。
- 如果后面的任务省略“上午/下午/晚上”，但上下文能推断，按上下文合理推断。

示例：
输入文本：明天上午9点开产品讨论会，10点半有一个面试，然后晚上跟李总的晚饭取消
输出动作：
- 创建事件：产品讨论会，时间为明天 09:00
- 创建事件：面试，时间为明天 10:30
- 删除事件：selector.date 为明天，selector.keywords 为 ["李总", "晚饭"]

输入文本：删除明天所有日程
输出动作：
- 删除事件：selector.date 为明天，selector.all 为 true，selector.keywords 为空数组

输入文本：今天的考试是雅思考试，安装的家具是电动升降桌
已有日程：考试 16:00-17:00，安装家具 20:00-21:00
输出动作：
- 修改事件：selector.keywords 为 ["考试"]，updates.title 为 "考雅思" 或 "雅思考试"
- 修改事件：selector.keywords 为 ["安装家具"]，updates.title 为 "安装电动升降桌"

规则：
- 不要执行任何操作，只做计划。
- 如果无法提取可执行的日程任务，返回空 actions，并在 reply 中给出简短中文说明。
""".strip()


def _smalltalk_prompt() -> str:
    return """
你是语音日历助手的“闲聊回复”节点。你只能返回 JSON，不要输出解释文字。

输出结构：
{
  "reply": string
}

规则：
- 用简短、友好的中文回复。
- 如果用户在闲聊，简短回应即可。
- 合适时自然引导用户说出日历指令。
- 不要声称自己已经执行了日程操作。
""".strip()
