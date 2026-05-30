import json
import re
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..logging_config import get_logger
from .schemas import (
    CALENDAR_INTENT,
    CREATE_EVENT,
    DELETE_EVENT,
    QUERY_EVENTS,
    SMALLTALK_INTENT,
    UNCLEAR_INTENT,
    UPDATE_EVENT,
    ActionPlan,
    CalendarAction,
)

logger = get_logger("agent.parser")


def parse_command(text: str, timezone: str) -> ActionPlan:
    normalized_text = text.strip()
    logger.info("parser_start text_length=%s timezone=%s", len(normalized_text), timezone)

    if not normalized_text:
        logger.warning("parser_unclear reason=empty_text")
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我没有听清楚。你可以试试说：“明天下午三点开会”。")

    if not _looks_calendar_related(normalized_text):
        logger.info("parser_routed_smalltalk")
        return ActionPlan(intent=SMALLTALK_INTENT, reply="我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。")

    if current_app.config.get("OPENAI_API_KEY"):
        try:
            plan = _parse_with_langchain(normalized_text, timezone)
            logger.info(
                "parser_langchain_success intent=%s action_count=%s actions=%s",
                plan.intent,
                len(plan.actions),
                [action.to_dict() for action in plan.actions],
            )
            return plan
        except Exception:
            logger.exception("parser_langchain_failed fallback=rules")
            return _parse_with_rules(normalized_text, timezone)

    logger.info("parser_rules_selected reason=missing_openai_api_key")
    return _parse_with_rules(normalized_text, timezone)


def _parse_with_langchain(text: str, timezone: str) -> ActionPlan:
    model = ChatOpenAI(
        model=current_app.config["AGENT_MODEL"],
        temperature=current_app.config["AGENT_TEMPERATURE"],
        api_key=current_app.config["OPENAI_API_KEY"],
        base_url=current_app.config["OPENAI_BASE_URL"],
    )
    response = model.bind(response_format={"type": "json_object"}).invoke(
        [
            SystemMessage(content=_system_prompt()),
            HumanMessage(
                content=json.dumps(
                    {
                        "text": text,
                        "timezone": timezone,
                        "current_date": date.today().isoformat(),
                    },
                    ensure_ascii=False,
                )
            ),
        ]
    )

    return ActionPlan.from_dict(json.loads(response.content))


def _parse_with_rules(text: str, timezone: str) -> ActionPlan:
    segments = _split_command_segments(text)
    actions = []
    context = _extract_context(text)

    for segment in segments:
        contextual_segment = _apply_context(segment, context)
        action_type = _detect_action_type(contextual_segment)
        action_arguments = _extract_arguments(contextual_segment, timezone, action_type)
        actions.append(CalendarAction(type=action_type, arguments=action_arguments, confidence=0.6))

    logger.info(
        "parser_rules_success action_count=%s action_types=%s actions=%s",
        len(actions),
        [action.type for action in actions],
        [action.to_dict() for action in actions],
    )

    return ActionPlan(
        intent=CALENDAR_INTENT,
        actions=actions,
    )


def _detect_action_type(text: str) -> str:
    if any(keyword in text for keyword in ("删除", "取消", "删掉")):
        return DELETE_EVENT

    if any(keyword in text for keyword in ("改", "修改", "换到", "挪到")):
        return UPDATE_EVENT

    if any(keyword in text for keyword in ("什么安排", "有哪些", "查询", "看看", "日程")) and not any(
        keyword in text for keyword in ("添加", "创建", "安排一个")
    ):
        return QUERY_EVENTS

    return CREATE_EVENT


def _extract_arguments(text: str, timezone: str, action_type: str) -> dict:
    selected_date = _extract_date(text, timezone)
    start_time = _extract_datetime(text, timezone)
    recurrence = _extract_recurrence(text, start_time)
    title = _extract_title(text)

    if action_type == CREATE_EVENT:
        arguments = {
            "title": title,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": None,
            "notes": None,
            **recurrence,
        }
        return {key: value for key, value in arguments.items() if value is not None}

    if action_type == QUERY_EVENTS:
        query_date = selected_date
        return {
            "date": query_date.isoformat(),
            "keywords": _extract_keywords(text),
        }

    selector = {
        "date": start_time.date().isoformat() if start_time else selected_date.isoformat(),
        "keywords": _extract_keywords(text),
    }

    if start_time:
        selector["start"] = start_time.isoformat()
        selector["end"] = (start_time + timedelta(hours=1)).isoformat()

    if action_type == DELETE_EVENT:
        if _is_delete_all_day(text):
            selector["all"] = True
            selector["keywords"] = []

        return {"selector": selector}

    updates = {}
    updated_time = _extract_update_time(text, timezone, start_time)

    if updated_time:
        updates["start_time"] = updated_time.isoformat()
        updates["end_time"] = (updated_time + timedelta(hours=1)).isoformat()

    updated_title = _extract_updated_title(text)

    if updated_title:
        updates["title"] = updated_title

    return {
        "selector": selector,
        "updates": updates,
    }


def _looks_calendar_related(text: str) -> bool:
    keywords = (
        "会",
        "会议",
        "日程",
        "安排",
        "提醒",
        "上午",
        "早上",
        "下午",
        "晚上",
        "每天",
        "每周",
        "每月",
        "删除",
        "修改",
        "查询",
    )
    return any(keyword in text for keyword in keywords)


def _is_delete_all_day(text: str) -> bool:
    if not any(keyword in text for keyword in ("删除", "取消", "删掉", "清空")):
        return False

    return any(
        keyword in text
        for keyword in (
            "所有",
            "全部",
            "整天",
            "一整天",
            "当天",
            "这天",
            "这一天",
            "那天",
            "那一天",
            "一天的",
        )
    )


def _extract_date(text: str, timezone: str) -> date:
    selected_date = _now(timezone).date()
    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)

    if iso_match:
        return date(
            int(iso_match.group(1)),
            int(iso_match.group(2)),
            int(iso_match.group(3)),
        )

    chinese_date_match = re.search(r"(\d{1,2})月(\d{1,2})(日|号)?", text)

    if chinese_date_match:
        return date(
            selected_date.year,
            int(chinese_date_match.group(1)),
            int(chinese_date_match.group(2)),
        )

    if "后天" in text:
        return selected_date + timedelta(days=2)

    if "明天" in text:
        return selected_date + timedelta(days=1)

    return selected_date


def _extract_datetime(text: str, timezone: str) -> datetime | None:
    selected_date = _extract_date(text, timezone)
    hour = _extract_hour(text)
    minute = _extract_minute(text)

    if hour is None:
        return None

    return datetime.combine(selected_date, time(hour=hour, minute=minute), tzinfo=ZoneInfo(timezone))


def _extract_update_time(text: str, timezone: str, original_time: datetime | None) -> datetime | None:
    marker_match = re.search(r"(改到|改成|换到|挪到)(.+)$", text)

    if not marker_match:
        return None

    target_text = marker_match.group(2)
    hour = _extract_hour(target_text)

    if hour is None:
        return None

    if original_time and original_time.hour >= 12 and hour < 12 and "上午" not in target_text:
        hour += 12

    selected_date = original_time.date() if original_time else _now(timezone).date()
    return datetime.combine(selected_date, time(hour=hour, minute=_extract_minute(target_text)), tzinfo=ZoneInfo(timezone))


def _extract_hour(text: str) -> int | None:
    digit_match = re.search(r"(\d{1,2})[点:：]", text)

    if digit_match:
        hour = int(digit_match.group(1))
    else:
        chinese_hours = {
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        chinese_match = re.search(r"([一二两三四五六七八九十])点", text)

        if not chinese_match:
            return None

        hour = chinese_hours[chinese_match.group(1)]

    if "下午" in text or "晚上" in text:
        if hour < 12:
            hour += 12

    return hour


def _extract_minute(text: str) -> int:
    minute_match = re.search(r"\d{1,2}[点:：](\d{1,2})", text)

    if minute_match:
        return int(minute_match.group(1))

    if "半" in text and re.search(r"(\d{1,2}|[一二两三四五六七八九十])点半", text):
        return 30

    return 0


def _extract_title(text: str) -> str:
    cleaned = text

    for word in (
        "帮我",
        "添加",
        "创建",
        "安排一个",
        "安排",
        "删除",
        "取消",
        "修改",
        "把",
        "有一个",
        "有个",
        "一个",
        "开",
        "要去",
        "要出去",
        "出去",
        "要",
        "去",
    ):
        cleaned = cleaned.replace(word, "")

    cleaned = re.sub(r"\d{4}-\d{1,2}-\d{1,2}", "", cleaned)
    cleaned = re.sub(r"\d{1,2}月\d{1,2}(日|号)?", "", cleaned)
    cleaned = re.sub(r"(今天|明天|后天|早上|上午|下午|晚上|每天|每周|每月|周[一二三四五六日天]?|\d{1,2}[点:：](\d{1,2}|半)?钟?|[一二两三四五六七八九十]点半?钟?|取消)", "", cleaned)
    cleaned = cleaned.replace("的", "").replace("到", "").strip(" ，。,")

    return cleaned or "日程"


def _extract_updated_title(text: str) -> str | None:
    title_match = re.search(r"改成(.+)$", text)

    if not title_match:
        return None

    updated = title_match.group(1).strip(" ，。,")

    if _extract_hour(updated) is not None:
        return None

    return updated or None


def _extract_keywords(text: str) -> list[str]:
    title = _extract_title(text)
    ignored = {"日程", "有什么", "有哪些", "查询", "看看", "安排"}
    keywords = []

    for keyword in re.split(r"\s+", title):
        cleaned = keyword.replace("改", "").replace("删", "")

        if cleaned and cleaned not in ignored:
            keywords.append(cleaned)

    if "李总" in title:
        keywords.append("李总")

    if "晚饭" in title:
        keywords.append("晚饭")

    if "晚餐" in title:
        keywords.append("晚餐")

    if "吃饭" in title or "吃个饭" in title:
        keywords.append("吃饭")

    return keywords


def _extract_recurrence(text: str, start_time: datetime | None) -> dict:
    if "每天" in text:
        return {"recurrence_type": "daily", "recurrence_interval": 1}

    if "每周" in text:
        return {"recurrence_type": "weekly", "recurrence_interval": 1}

    if "每月" in text:
        return {"recurrence_type": "monthly", "recurrence_interval": 1}

    return {"recurrence_type": "none", "recurrence_interval": 1}


def _now(timezone: str) -> datetime:
    return datetime.now(ZoneInfo(timezone))


def _system_prompt() -> str:
    return """
You are a calendar command planner. Return JSON only.

Schema:
{
  "intent": "calendar" | "smalltalk" | "unsupported" | "unclear",
  "reply": string | null,
  "actions": [
    {
      "type": "create_event" | "query_events" | "update_event" | "delete_event",
      "confidence": number,
      "arguments": object
    }
  ]
}

Rules:
- Always use actions as a list.
- If the user asks for multiple operations in one sentence, return one action per operation in the original order.
- Do not merge multiple event creations/deletions/updates into one action.
- Use ISO datetime strings with the provided timezone.
- For create_event arguments, use title, start_time, end_time, notes, recurrence_type, recurrence_interval, recurrence_until.
- For query_events arguments, use date or start/end plus optional keywords.
- For update_event arguments, use selector and updates.
- For delete_event arguments, use selector.
- selector may include date, start, end, keywords, and all.
- If the user clearly asks to delete all events on a day, set selector.all to true and do not add keywords.
- Do not execute anything. Only plan.
""".strip()


def _split_command_segments(text: str) -> list[str]:
    normalized = text.strip(" ，。,")
    parts = re.split(r"(?:，|,|。|；|;|然后|并且|并|再)", normalized)
    segments = [part.strip(" ，。,") for part in parts if part.strip(" ，。,")]

    return segments or [normalized]


def _extract_context(text: str) -> dict:
    context = {}

    for date_word in ("后天", "明天", "今天"):
        if date_word in text:
            context["date_word"] = date_word
            break

    for meridiem in ("早上", "上午", "下午", "晚上"):
        if meridiem in text:
            context["meridiem"] = meridiem
            break

    return context


def _apply_context(segment: str, context: dict) -> str:
    contextual_segment = segment

    if context.get("date_word") and not any(word in contextual_segment for word in ("今天", "明天", "后天")):
        contextual_segment = f"{context['date_word']}{contextual_segment}"

    if (
        context.get("meridiem")
        and not any(word in contextual_segment for word in ("上午", "下午", "晚上"))
        and _extract_hour(contextual_segment) is not None
    ):
        contextual_segment = f"{context['meridiem']}{contextual_segment}"

    return contextual_segment
