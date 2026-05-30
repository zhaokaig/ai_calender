from flask import Blueprint, g, jsonify, request

from ..auth import login_required
from ..event_service import create_event, delete_event, get_event, list_events, update_event

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

    try:
        event = update_event(g.current_user["id"], event_id, data)
    except ValueError as error:
        return _error(str(error), 400)

    if event is None:
        return _error("event not found", 404)

    return jsonify({"event": event})


@events_bp.delete("/<int:event_id>")
@login_required
def delete_event_route(event_id: int):
    deleted = delete_event(g.current_user["id"], event_id)

    if not deleted:
        return _error("event not found", 404)

    return "", 204


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code
