from threading import Lock

MAX_EVENTS_PER_USER = 12

_events_by_user: dict[int, list[dict]] = {}
_lock = Lock()


def remember_events(user_id: int, events: list[dict]) -> None:
    normalized_events = []

    for event in events:
        memory_event = _memory_event(event)

        if memory_event:
            normalized_events.append(memory_event)

    if not normalized_events:
        return

    with _lock:
        current_events = _events_by_user.get(user_id, [])
        merged_events = normalized_events + current_events
        seen_ids = set()
        deduped_events = []

        for event in merged_events:
            event_id = event["id"]

            if event_id in seen_ids:
                continue

            seen_ids.add(event_id)
            deduped_events.append(event)

        _events_by_user[user_id] = deduped_events[:MAX_EVENTS_PER_USER]


def get_recent_events(user_id: int, limit: int = 5) -> list[dict]:
    with _lock:
        return [event.copy() for event in _events_by_user.get(user_id, [])[:limit]]


def clear_memory() -> None:
    with _lock:
        _events_by_user.clear()


def _memory_event(event: dict) -> dict | None:
    event_id = event.get("series_id") or event.get("id")

    if not event_id:
        return None

    return {
        "id": event_id,
        "title": event.get("title"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
    }
