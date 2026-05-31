from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..event_service import (
    create_event,
    delete_event,
    delete_event_occurrence,
    get_event,
    list_events,
    truncate_recurring_event,
    update_event,
    update_event_occurrence,
)

events_bp = Blueprint("events", __name__, url_prefix="/api/events")


@events_bp.get("")
@login_required
def list_event_route():
    try:
        events = list_events(g.current_user["id"], request.args)
    except ValueError as error:
        return _error(str(error), 400)

    return jsonify({"events": events})


@events_bp.get("/<int:event_id>")
@login_required
def get_event_route(event_id: int):
    event = get_event(g.current_user["id"], event_id)

    if event is None:
        return _error("event not found", 404)

    return jsonify({"event": event})


@events_bp.post("")
@login_required
def create_event_route():
    data = request.get_json(silent=True) or {}

    try:
        event = create_event(g.current_user["id"], data)
    except ValueError as error:
        return _error(str(error), 400)

    return jsonify({"event": event}), 201


@events_bp.patch("/<int:event_id>")
@login_required
def update_event_route(event_id: int):
    data = request.get_json(silent=True) or {}
    scope = data.pop("scope", "series")

    try:
        if scope == "occurrence":
            occurrence_start_time = data.pop("occurrence_start_time", None)

            if not occurrence_start_time:
                return _error("occurrence_start_time is required for occurrence updates", 400)

            event = update_event_occurrence(g.current_user["id"], event_id, occurrence_start_time, data)
        else:
            event = update_event(g.current_user["id"], event_id, data)
    except ValueError as error:
        return _error(str(error), 400)

    if event is None:
        return _error("event not found", 404)

    return jsonify({"event": event})


@events_bp.delete("/<int:event_id>")
@login_required
def delete_event_route(event_id: int):
    scope = request.args.get("scope", "series")

    try:
        if scope == "occurrence":
            occurrence_start_time = request.args.get("occurrence_start_time")

            if not occurrence_start_time:
                return _error("occurrence_start_time is required for occurrence deletes", 400)

            deleted_event = delete_event_occurrence(g.current_user["id"], event_id, occurrence_start_time)
            deleted = deleted_event is not None
        elif scope == "future":
            cutoff_start_time = request.args.get("from") or request.args.get("start")

            if not cutoff_start_time:
                return _error("from is required for future deletes", 400)

            deleted_event = truncate_recurring_event(g.current_user["id"], event_id, cutoff_start_time)
            deleted = deleted_event is not None
        else:
            deleted = delete_event(g.current_user["id"], event_id)
    except ValueError as error:
        return _error(str(error), 400)

    if not deleted:
        return _error("event not found", 404)

    return "", 204


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code
