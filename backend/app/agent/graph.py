from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from ..logging_config import get_logger
from .executor import execute_plan
from .parser import parse_command
from .schemas import CALENDAR_INTENT, AgentResponse, SMALLTALK_INTENT, SUCCESS, UNSUPPORTED, ActionPlan

logger = get_logger("agent.graph")


class VoiceCommandState(TypedDict, total=False):
    user_id: int
    text: str
    timezone: str
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
    graph.add_node("intent_router", _intent_router)
    graph.add_node("action_planner", _action_planner)
    graph.add_node("tool_executor", _tool_executor)
    graph.add_node("chat_fallback", _chat_fallback)
    graph.add_node("response_composer", _response_composer)

    graph.set_entry_point("intent_router")
    graph.add_conditional_edges(
        "intent_router",
        _route_after_intent,
        {
            "calendar": "action_planner",
            "fallback": "chat_fallback",
        },
    )
    graph.add_edge("action_planner", "tool_executor")
    graph.add_edge("tool_executor", "response_composer")
    graph.add_edge("chat_fallback", "response_composer")
    graph.add_edge("response_composer", END)

    return graph.compile()


def _intent_router(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=intent_router user_id=%s", state["user_id"])
    plan = parse_command(state["text"], state["timezone"])
    logger.info("graph_node_finish node=intent_router intent=%s action_count=%s", plan.intent, len(plan.actions))
    return {"plan": plan}


def _route_after_intent(state: VoiceCommandState) -> str:
    return "calendar" if state["plan"].intent == CALENDAR_INTENT else "fallback"


def _action_planner(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=action_planner action_count=%s", len(state["plan"].actions))
    return {"plan": state["plan"]}


def _tool_executor(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=tool_executor user_id=%s", state["user_id"])
    return {
        "response": execute_plan(
            state["user_id"],
            state["plan"],
        )
    }


def _chat_fallback(state: VoiceCommandState) -> dict[str, Any]:
    plan = state["plan"]
    logger.info("graph_node_start node=chat_fallback intent=%s", plan.intent)
    return {
        "response": AgentResponse(
            intent=plan.intent,
            status=SUCCESS if plan.intent == SMALLTALK_INTENT else UNSUPPORTED,
            message=plan.reply or "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。",
            actions=plan.actions,
        )
    }


def _response_composer(state: VoiceCommandState) -> dict[str, Any]:
    logger.info("graph_node_start node=response_composer status=%s", state["response"].status)
    return {"response": state["response"]}
