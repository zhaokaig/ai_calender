from dataclasses import dataclass, field
from typing import Any

CALENDAR_INTENT = "calendar"
SMALLTALK_INTENT = "smalltalk"
UNSUPPORTED_INTENT = "unsupported"
UNCLEAR_INTENT = "unclear"

CREATE_EVENT = "create_event"
QUERY_EVENTS = "query_events"
UPDATE_EVENT = "update_event"
DELETE_EVENT = "delete_event"

SUPPORTED_INTENTS = {
    CALENDAR_INTENT,
    SMALLTALK_INTENT,
    UNSUPPORTED_INTENT,
    UNCLEAR_INTENT,
}

SUPPORTED_ACTIONS = {
    CREATE_EVENT,
    QUERY_EVENTS,
    UPDATE_EVENT,
    DELETE_EVENT,
}

SUCCESS = "success"
NEEDS_SELECTION = "needs_selection"
NOT_FOUND = "not_found"
UNSUPPORTED = "unsupported"
ERROR = "error"


@dataclass
class CalendarAction:
    type: str
    arguments: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalendarAction":
        action_type = data.get("type")

        if action_type not in SUPPORTED_ACTIONS:
            raise ValueError(f"unsupported action type: {action_type}")

        arguments = data.get("arguments") or {}

        if not isinstance(arguments, dict):
            raise ValueError("action arguments must be an object")

        confidence = data.get("confidence")

        return cls(type=action_type, arguments=arguments, confidence=confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "arguments": self.arguments,
            "confidence": self.confidence,
        }


@dataclass
class ActionPlan:
    intent: str
    actions: list[CalendarAction] = field(default_factory=list)
    reply: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionPlan":
        intent = data.get("intent")

        if intent not in SUPPORTED_INTENTS:
            raise ValueError(f"unsupported intent: {intent}")

        actions_data = data.get("actions") or []

        if not isinstance(actions_data, list):
            raise ValueError("actions must be a list")

        actions = [CalendarAction.from_dict(action) for action in actions_data]

        return cls(intent=intent, actions=actions, reply=data.get("reply"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "actions": [action.to_dict() for action in self.actions],
            "reply": self.reply,
        }


@dataclass
class AgentResponse:
    intent: str
    status: str
    message: str
    actions: list[CalendarAction] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "status": self.status,
            "message": self.message,
            "actions": [action.to_dict() for action in self.actions],
            "results": self.results,
            "events": self.events,
            "candidates": self.candidates,
        }
