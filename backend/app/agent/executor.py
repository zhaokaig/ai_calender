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
from ..event_service import create_event, delete_event, list_events, update_event

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
            message="我没有识别到可执行的日程操作。",
            actions=plan.actions,
        )

    results = []
    events = []
    candidates = []
    response_status = SUCCESS

    for action in plan.actions[:1]:
        logger.info("executor_action_start user_id=%s action_type=%s", user_id, action.type)
        result = _execute_action(user_id, action)
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
        candidates = _find_candidates(user_id, action.arguments.get("selector", {}))

        if not candidates:
            return _not_found_result(action.type)

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
        "message": "暂不支持这个日程操作。",
    }


def _find_candidates(user_id: int, selector: dict) -> list[dict]:
    logger.info("executor_find_candidates user_id=%s selector=%s", user_id, selector)
    filters = {}

    if selector.get("start") and selector.get("end"):
        filters["start"] = selector["start"]
        filters["end"] = selector["end"]
    elif selector.get("date"):
        filters["date"] = selector["date"]

    events = list_events(user_id, filters)
    keywords = [keyword for keyword in selector.get("keywords", []) if keyword]

    if not keywords:
        logger.info("executor_candidates_result user_id=%s count=%s keyword_filtered=false", user_id, len(events))
        return events

    matched = []

    for event in events:
        title = event["title"]

        if any(keyword in title for keyword in keywords):
            matched.append(event)

    candidates = matched or events
    logger.info(
        "executor_candidates_result user_id=%s count=%s keyword_filtered=true matched_count=%s",
        user_id,
        len(candidates),
        len(matched),
    )

    return candidates


def _not_found_result(action_type: str) -> dict:
    return {
        "action": action_type,
        "status": NOT_FOUND,
        "message": "没有找到匹配的日程。",
        "events": [],
        "candidates": [],
    }


def _needs_selection_result(action_type: str, candidates: list[dict]) -> dict:
    return {
        "action": action_type,
        "status": NEEDS_SELECTION,
        "message": "我找到了多个可能的日程，请选择一个。",
        "events": [],
        "candidates": candidates,
    }


def _query_message(events: list[dict]) -> str:
    if not events:
        return "没有找到相关日程。"

    if len(events) == 1:
        return f"找到 1 个日程：{events[0]['title']}。"

    return f"找到 {len(events)} 个日程。"


def _compose_message(results: list[dict]) -> str:
    if not results:
        return "我没有执行任何操作。"

    return results[0]["message"]
