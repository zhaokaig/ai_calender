from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .executor import execute_plan
from .parser import parse_command
from .schemas import CALENDAR_INTENT, AgentResponse, SMALLTALK_INTENT, SUCCESS, UNSUPPORTED, ActionPlan


class VoiceCommandState(TypedDict, total=False):
    user_id: int
    text: str
    timezone: str
    plan: ActionPlan
    response: AgentResponse


def run_voice_command_graph(user_id: int, text: str, timezone: str) -> AgentResponse:
    graph = _build_graph()
    final_state = graph.invoke(
        {
            "user_id": user_id,
            "text": text,
            "timezone": timezone,
        }
    )

    return final_state["response"]


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
    plan = parse_command(state["text"], state["timezone"])
    return {"plan": plan}


def _route_after_intent(state: VoiceCommandState) -> str:
    return "calendar" if state["plan"].intent == CALENDAR_INTENT else "fallback"


def _action_planner(state: VoiceCommandState) -> dict[str, Any]:
    return {"plan": state["plan"]}


def _tool_executor(state: VoiceCommandState) -> dict[str, Any]:
    return {
        "response": execute_plan(
            state["user_id"],
            state["plan"],
        )
    }


def _chat_fallback(state: VoiceCommandState) -> dict[str, Any]:
    plan = state["plan"]
    return {
        "response": AgentResponse(
            intent=plan.intent,
            status=SUCCESS if plan.intent == SMALLTALK_INTENT else UNSUPPORTED,
            message=plan.reply or "我现在主要能帮你管理日程。你可以试试说：“明天下午三点开会”。",
            actions=plan.actions,
        )
    }


def _response_composer(state: VoiceCommandState) -> dict[str, Any]:
    return {"response": state["response"]}
