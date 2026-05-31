from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..event_service import list_events
from ..logging_config import get_logger
from .executor import execute_plan
from .memory import get_recent_events, get_recent_turns, remember_events, remember_turn
from .parser import classify_intent, recognize_event_tasks
from .schemas import CALENDAR_INTENT, AgentResponse, SMALLTALK_INTENT, SUCCESS, UNSUPPORTED, ActionPlan, IntentResult

logger = get_logger("agent.graph")


class VoiceCommandState(TypedDict, total=False):
    user_id: int
    text: str
    rewritten_text: str
    timezone: str
    intent_result: IntentResult
    plan: ActionPlan
    response: AgentResponse


def run_voice_command_graph(user_id: int, text: str, timezone: str) -> AgentResponse:
    logger.info("graph_start user_id=%s text_length=%s timezone=%s", user_id, len(text), timezone)
    graph = _build_graph()
    final_state = graph.invoke(
        {
            "user_id": user_id,
            "text": text,
            "timezone": timezone,
        }
    )

    response = final_state["response"]
    logger.info("graph_finish user_id=%s status=%s intent=%s", user_id, response.status, response.intent)

    return response


@lru_cache(maxsize=1)
def _build_graph():
    graph = StateGraph(VoiceCommandState)
    graph.add_node("intent_classifier", _intent_classifier)
    graph.add_node("event_recognizer", _event_recognizer)
    graph.add_node("tool_executor", _tool_executor)
    graph.add_node("chat_responder", _chat_responder)
    graph.add_node("response_composer", _response_composer)

    graph.set_entry_point("intent_classifier")
    graph.add_conditional_edges(
        "intent_classifier",
        _route_after_intent,
        {
            "calendar": "event_recognizer",
            "fallback": "chat_responder",
        },
    )
    graph.add_edge("event_recognizer", "tool_executor")
    graph.add_edge("tool_executor", "response_composer")
    graph.add_edge("chat_responder", "response_composer")
    graph.add_edge("response_composer", END)

    return graph.compile()


def _intent_classifier(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=intent_classifier user_id=%s", state["user_id"])
    intent_result = classify_intent(state["text"], state["timezone"])
    logger.info("graph_node_finish node=intent_classifier intent=%s", intent_result.intent)

    return {
        "intent_result": intent_result,
        "rewritten_text": intent_result.text or state["text"],
    }


def _route_after_intent(state: VoiceCommandState) -> str:
    return "calendar" if state["intent_result"].intent == CALENDAR_INTENT else "fallback"


def _event_recognizer(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=event_recognizer user_id=%s", state["user_id"])
    existing_events = list_events(state["user_id"], {})
    recent_events = get_recent_events(state["user_id"])
    recent_turns = get_recent_turns(state["user_id"])
    plan = recognize_event_tasks(
        state["rewritten_text"],
        state["timezone"],
        existing_events,
        recent_events,
        recent_turns,
    )
    logger.info("graph_node_finish node=event_recognizer action_count=%s", len(plan.actions))
    return {"plan": plan}


def _tool_executor(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=tool_executor user_id=%s", state["user_id"])
    response = execute_plan(
        state["user_id"],
        state["plan"],
    )
    remember_events(state["user_id"], response.events)

    return {
        "response": response
    }


def _chat_responder(state: VoiceCommandState) -> dict[str, Any]:
    intent_result = state["intent_result"]
    logger.info("graph_node_start node=chat_responder intent=%s", intent_result.intent)

    return {
        "response": AgentResponse(
            intent=intent_result.intent,
            status=SUCCESS if intent_result.intent == SMALLTALK_INTENT else UNSUPPORTED,
            message=intent_result.text or "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。",
            actions=[],
        )
    }


def _response_composer(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=response_composer status=%s", state["response"].status)
    remember_turn(state["user_id"], state["text"], state["response"])
    return {"response": state["response"]}
