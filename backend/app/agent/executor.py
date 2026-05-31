from .schemas import (
    CALENDAR_INTENT,
    CREATE_EVENT,
    DELETE_EVENT,
    ERROR,
    NEEDS_SELECTION,
    NOT_FOUND,
    QUERY_EVENTS,
    SMALLTALK_INTENT,
    SUCCESS,
    UPDATE_EVENT,
    AgentResponse,
    CalendarAction,
)
from ..logging_config import get_logger
from ..event_service import create_event, delete_event, get_event, list_events, update_event

logger = get_logger("agent.executor")


def execute_plan(user_id: int, plan) -> AgentResponse:
    logger.info("executor_start user_id=%s intent=%s action_count=%s", user_id, plan.intent, len(plan.actions))
    if plan.intent != CALENDAR_INTENT:
        return AgentResponse(
            intent=plan.intent,
            status=SUCCESS if plan.intent == SMALLTALK_INTENT else ERROR,
            message=plan.reply or "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。",
            actions=plan.actions,
        )

    if not plan.actions:
        return AgentResponse(
            intent=plan.intent,
            status=ERROR,
            message="我没听出要执行的日程操作，请说清楚要创建、查询、修改还是删除日程。",
            actions=plan.actions,
        )

    results = []
    events = []
    candidates = []
    response_status = SUCCESS

    for index, action in enumerate(plan.actions, start=1):
        logger.info("executor_action_start user_id=%s action_type=%s", user_id, action.type)
        result = _execute_action(user_id, action)
        result["index"] = index
        logger.info("executor_action_result user_id=%s action_type=%s status=%s", user_id, action.type, result["status"])
        results.append(result)
        events.extend(result.get("events", []))
        candidates.extend(result.get("candidates", []))

        if result["status"] != SUCCESS:
            response_status = result["status"]
            break

    return AgentResponse(
        intent=plan.intent,
        status=response_status,
        message=_compose_message(results),
        actions=plan.actions,
        results=results,
        events=events,
        candidates=candidates,
    )


def _execute_action(user_id: int, action: CalendarAction) -> dict:
    if action.type == CREATE_EVENT:
        event = create_event(user_id, action.arguments)
        return {
            "action": action.type,
            "status": SUCCESS,
            "message": f"已创建日程：{event['title']}。",
            "events": [event],
        }

    if action.type == QUERY_EVENTS:
        events = list_events(user_id, action.arguments)
        return {
            "action": action.type,
            "status": SUCCESS,
            "message": _query_message(events),
            "events": events,
        }

    if action.type == UPDATE_EVENT:
        candidates = _find_candidates(user_id, action.arguments.get("selector", {}))

        if not candidates:
            return _not_found_result(action.type)

        if len(candidates) > 1:
            return _needs_selection_result(action.type, candidates)

        updated_event = update_event(
            user_id,
            candidates[0]["series_id"],
            action.arguments.get("updates", {}),
        )
        return {
            "action": action.type,
            "status": SUCCESS,
            "message": f"已更新日程：{updated_event['title']}。",
            "events": [updated_event],
        }

    if action.type == DELETE_EVENT:
        selector = action.arguments.get("selector", {})
        candidates = _find_candidates(user_id, selector)

        if not candidates:
            return _not_found_result(action.type)

        if selector.get("all") is True:
            deleted_events = _delete_all_candidates(user_id, candidates)
            return {
                "action": action.type,
                "status": SUCCESS,
                "message": f"已删除 {len(deleted_events)} 个日程。",
                "events": deleted_events,
            }

        if len(candidates) > 1:
            return _needs_selection_result(action.type, candidates)

        delete_event(user_id, candidates[0]["series_id"])
        return {
            "action": action.type,
            "status": SUCCESS,
            "message": f"已删除日程：{candidates[0]['title']}。",
            "events": [candidates[0]],
        }

    return {
        "action": action.type,
        "status": ERROR,
        "message": "这个日程操作我现在还不会做，可以先试试创建、查询、修改或删除日程。",
    }


def _delete_all_candidates(user_id: int, candidates: list[dict]) -> list[dict]:
    deleted_events = []
    deleted_series_ids = set()

    for candidate in candidates:
        event_id = candidate["series_id"]

        if event_id in deleted_series_ids:
            continue

        delete_event(user_id, event_id)
        deleted_series_ids.add(event_id)
        deleted_events.append(candidate)

    logger.info("executor_delete_all_result user_id=%s deleted_count=%s", user_id, len(deleted_events))

    return deleted_events


def _find_candidates(user_id: int, selector: dict) -> list[dict]:
    logger.info("executor_find_candidates user_id=%s selector=%s", user_id, selector)
    selected_event_id = selector.get("event_id") or selector.get("series_id") or selector.get("id")

    if selected_event_id:
        event = _get_selected_event(user_id, selected_event_id)
        candidates = [event] if event else []
        logger.info("executor_candidates_result user_id=%s count=%s exact_id=true", user_id, len(candidates))
        return candidates

    filters = {}

    if selector.get("start") and selector.get("end"):
        filters["start"] = selector["start"]
        filters["end"] = selector["end"]
    elif selector.get("date"):
        filters["date"] = selector["date"]

    events = list_events(user_id, filters)
    if selector.get("all") is True:
        logger.info("executor_candidates_result user_id=%s count=%s delete_all=true", user_id, len(events))
        return events

    keywords = [keyword for keyword in selector.get("keywords", []) if keyword]

    if not keywords:
        logger.info("executor_candidates_result user_id=%s count=%s keyword_filtered=false", user_id, len(events))
        return events

    matched = []

    for event in events:
        title = _normalize_match_text(event["title"])

        if any(_normalize_match_text(keyword) in title for keyword in keywords):
            matched.append(event)

    candidates = matched or events
    logger.info(
        "executor_candidates_result user_id=%s count=%s keyword_filtered=true matched_count=%s",
        user_id,
        len(candidates),
        len(matched),
    )

    return candidates


def _normalize_match_text(value: str) -> str:
    return value.replace("的", "").replace(" ", "").strip()


def _get_selected_event(user_id: int, event_id) -> dict | None:
    try:
        selected_id = int(event_id)
    except (TypeError, ValueError):
        return None

    event = get_event(user_id, selected_id)

    if not event:
        return None

    event["series_id"] = event["id"]
    event["is_recurring"] = event["recurrence_type"] != "none"

    return event


def _not_found_result(action_type: str) -> dict:
    return {
        "action": action_type,
        "status": NOT_FOUND,
        "message": "我没找到匹配的日程。可以换个时间、标题或说得更具体一点。",
        "events": [],
        "candidates": [],
    }


def _needs_selection_result(action_type: str, candidates: list[dict]) -> dict:
    return {
        "action": action_type,
        "status": NEEDS_SELECTION,
        "message": "我找到了多个可能的日程，不确定你指哪一个，请再说得更具体一点。",
        "events": [],
        "candidates": candidates,
    }


def _query_message(events: list[dict]) -> str:
    if not events:
        return "这段时间没有找到日程。"

    if len(events) == 1:
        return f"找到 1 个日程：{events[0]['title']}。"

    return f"找到 {len(events)} 个日程。"


def _compose_message(results: list[dict]) -> str:
    if not results:
        return "我没有执行任何操作，请再说一次你的日程需求。"

    if len(results) == 1:
        return results[0]["message"]

    success_count = len([result for result in results if result["status"] == SUCCESS])

    if success_count == len(results):
        return f"已完成 {success_count} 个日程操作。"

    return f"已完成 {success_count} 个日程操作，另有 {len(results) - success_count} 个需要处理。"
