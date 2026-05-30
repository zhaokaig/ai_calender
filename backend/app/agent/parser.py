import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import current_app

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


def parse_command(text: str, timezone: str) -> ActionPlan:
    normalized_text = text.strip()

    if not normalized_text:
        return ActionPlan(intent=UNCLEAR_INTENT, reply="我没有听清楚。你可以试试说：“明天下午三点开会”。")

    if not _looks_calendar_related(normalized_text):
        return ActionPlan(intent=SMALLTALK_INTENT, reply="我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。")

    if current_app.config.get("LLM_API_KEY"):
        try:
            return _parse_with_llm(normalized_text, timezone)
        except (ValueError, urllib.error.URLError, TimeoutError):
            return _parse_with_rules(normalized_text, timezone)

    return _parse_with_rules(normalized_text, timezone)


def _parse_with_llm(text: str, timezone: str) -> ActionPlan:
    payload = {
        "model": current_app.config["LLM_MODEL"],
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "text": text,
                        "timezone": timezone,
                        "current_date": date.today().isoformat(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        current_app.config["LLM_API_URL"],
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {current_app.config['LLM_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=current_app.config["LLM_TIMEOUT_SECONDS"]) as response:
        body = json.loads(response.read().decode("utf-8"))

    content = body["choices"][0]["message"]["content"]
    return ActionPlan.from_dict(json.loads(content))


def _parse_with_rules(text: str, timezone: str) -> ActionPlan:
    action_type = _detect_action_type(text)
    action_arguments = _extract_arguments(text, timezone, action_type)

    return ActionPlan(
        intent=CALENDAR_INTENT,
        actions=[
            CalendarAction(type=action_type, arguments=action_arguments, confidence=0.6)
        ],
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

    if hour is None:
        return None

    return datetime.combine(selected_date, time(hour=hour), tzinfo=ZoneInfo(timezone))


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
    return datetime.combine(selected_date, time(hour=hour), tzinfo=ZoneInfo(timezone))


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


def _extract_title(text: str) -> str:
    cleaned = text

    for word in ("帮我", "添加", "创建", "安排一个", "安排", "删除", "取消", "修改", "把"):
        cleaned = cleaned.replace(word, "")

    cleaned = re.sub(r"\d{4}-\d{1,2}-\d{1,2}", "", cleaned)
    cleaned = re.sub(r"\d{1,2}月\d{1,2}(日|号)?", "", cleaned)
    cleaned = re.sub(r"(今天|明天|后天|上午|下午|晚上|每天|每周|每月|周[一二三四五六日天]?|\d{1,2}[点:：]|[一二两三四五六七八九十]点)", "", cleaned)
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
- Use ISO datetime strings with the provided timezone.
- For create_event arguments, use title, start_time, end_time, notes, recurrence_type, recurrence_interval, recurrence_until.
- For query_events arguments, use date or start/end plus optional keywords.
- For update_event arguments, use selector and updates.
- For delete_event arguments, use selector.
- selector may include date, start, end, and keywords.
- Do not execute anything. Only plan.
""".strip()
