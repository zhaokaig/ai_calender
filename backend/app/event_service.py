from calendar import monthrange
from datetime import date, datetime, time, timedelta

from .database import get_db
from .logging_config import get_logger

VALID_RECURRENCE_TYPES = {"none", "daily", "weekly", "monthly"}
logger = get_logger("events")


def create_event(user_id: int, data: dict) -> dict:
    logger.info("event_create_attempt user_id=%s title=%s", user_id, data.get("title"))
    title = _required_text(data, "title")
    start_time = _required_datetime(data, "start_time")
    end_time = _optional_datetime(data, "end_time") or start_time + timedelta(hours=1)

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")

    recurrence_type = data.get("recurrence_type", "none")
    recurrence_interval = int(data.get("recurrence_interval", 1))
    recurrence_until = _optional_datetime(data, "recurrence_until")
    _validate_recurrence(recurrence_type, recurrence_interval, recurrence_until, start_time)

    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO events (
            user_id, title, start_time, end_time, notes,
            recurrence_type, recurrence_interval, recurrence_until
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            title,
            _format_datetime(start_time),
            _format_datetime(end_time),
            _optional_text(data, "notes"),
            recurrence_type,
            recurrence_interval,
            _format_datetime(recurrence_until) if recurrence_until else None,
        ),
    )
    db.commit()

    event = get_event(user_id, cursor.lastrowid)
    logger.info(
        "event_create_success user_id=%s event_id=%s recurrence_type=%s",
        user_id,
        event["id"],
        event["recurrence_type"],
    )

    return event


def list_events(user_id: int, filters: dict) -> list[dict]:
    logger.info("event_list_attempt user_id=%s filters=%s", user_id, dict(filters))
    range_start, range_end = _parse_query_range(filters)
    rows = get_db().execute(
        "SELECT * FROM events WHERE user_id = ? ORDER BY start_time",
        (user_id,),
    ).fetchall()
    occurrences = []

    for row in rows:
        occurrences.extend(_expand_event(dict(row), range_start, range_end))

    sorted_occurrences = sorted(occurrences, key=lambda event: event["start_time"])
    logger.info(
        "event_list_success user_id=%s count=%s range_start=%s range_end=%s",
        user_id,
        len(sorted_occurrences),
        _format_datetime(range_start),
        _format_datetime(range_end),
    )

    return sorted_occurrences


def get_event(user_id: int, event_id: int) -> dict | None:
    logger.info("event_get_attempt user_id=%s event_id=%s", user_id, event_id)
    row = get_db().execute(
        "SELECT * FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id),
    ).fetchone()
    event = _serialize_event(dict(row)) if row else None
    logger.info(
        "event_get_result user_id=%s event_id=%s found=%s",
        user_id,
        event_id,
        event is not None,
    )

    return event


def update_event(user_id: int, event_id: int, data: dict) -> dict | None:
    logger.info("event_update_attempt user_id=%s event_id=%s fields=%s", user_id, event_id, list(data.keys()))
    existing = get_event(user_id, event_id)

    if existing is None:
        logger.warning("event_update_failed user_id=%s event_id=%s reason=not_found", user_id, event_id)
        return None

    title = _optional_text(data, "title", default=existing["title"])
    start_time = _optional_datetime(data, "start_time") or _parse_datetime(existing["start_time"])
    end_time = _optional_datetime(data, "end_time") or _parse_datetime(existing["end_time"])

    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")

    recurrence_type = data.get("recurrence_type", existing["recurrence_type"])
    recurrence_interval = int(data.get("recurrence_interval", existing["recurrence_interval"]))
    recurrence_until = (
        _optional_datetime(data, "recurrence_until")
        if "recurrence_until" in data
        else _parse_datetime(existing["recurrence_until"])
        if existing["recurrence_until"]
        else None
    )
    _validate_recurrence(recurrence_type, recurrence_interval, recurrence_until, start_time)

    get_db().execute(
        """
        UPDATE events
        SET title = ?,
            start_time = ?,
            end_time = ?,
            notes = ?,
            recurrence_type = ?,
            recurrence_interval = ?,
            recurrence_until = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND user_id = ?
        """,
        (
            title,
            _format_datetime(start_time),
            _format_datetime(end_time),
            _optional_text(data, "notes", default=existing["notes"]),
            recurrence_type,
            recurrence_interval,
            _format_datetime(recurrence_until) if recurrence_until else None,
            event_id,
            user_id,
        ),
    )
    get_db().commit()

    event = get_event(user_id, event_id)
    logger.info("event_update_success user_id=%s event_id=%s", user_id, event_id)

    return event


def delete_event(user_id: int, event_id: int) -> bool:
    logger.info("event_delete_attempt user_id=%s event_id=%s", user_id, event_id)
    cursor = get_db().execute(
        "DELETE FROM events WHERE id = ? AND user_id = ?",
        (event_id, user_id),
    )
    get_db().commit()

    deleted = cursor.rowcount > 0
    logger.info("event_delete_result user_id=%s event_id=%s deleted=%s", user_id, event_id, deleted)

    return deleted


def _expand_event(event: dict, range_start: datetime, range_end: datetime) -> list[dict]:
    start_time = _parse_datetime(event["start_time"])
    end_time = _parse_datetime(event["end_time"])
    recurrence_until = _parse_datetime(event["recurrence_until"]) if event["recurrence_until"] else None

    if event["recurrence_type"] == "none":
        return [_serialize_occurrence(event, start_time, end_time)] if _overlaps(start_time, end_time, range_start, range_end) else []

    occurrences = []
    occurrence_start = start_time
    occurrence_end = end_time

    while _to_comparable_datetime(occurrence_start) < _to_comparable_datetime(range_end):
        if recurrence_until and _to_comparable_datetime(occurrence_start) > _to_comparable_datetime(recurrence_until):
            break

        if _overlaps(occurrence_start, occurrence_end, range_start, range_end):
            occurrences.append(_serialize_occurrence(event, occurrence_start, occurrence_end))

        occurrence_start = _next_occurrence(
            occurrence_start,
            event["recurrence_type"],
            event["recurrence_interval"],
        )
        occurrence_end = occurrence_start + (end_time - start_time)

    return occurrences


def _serialize_event(event: dict) -> dict:
    return {
        "id": event["id"],
        "user_id": event["user_id"],
        "title": event["title"],
        "start_time": event["start_time"],
        "end_time": event["end_time"],
        "notes": event["notes"],
        "recurrence_type": event["recurrence_type"],
        "recurrence_interval": event["recurrence_interval"],
        "recurrence_until": event["recurrence_until"],
        "created_at": event["created_at"],
        "updated_at": event["updated_at"],
    }


def _serialize_occurrence(event: dict, start_time: datetime, end_time: datetime) -> dict:
    serialized = _serialize_event(event)
    serialized["start_time"] = _format_datetime(start_time)
    serialized["end_time"] = _format_datetime(end_time)
    serialized["series_id"] = event["id"]
    serialized["is_recurring"] = event["recurrence_type"] != "none"

    return serialized


def _parse_query_range(filters: dict) -> tuple[datetime, datetime]:
    if filters.get("date"):
        selected_date = date.fromisoformat(filters["date"])
        return datetime.combine(selected_date, time.min), datetime.combine(selected_date + timedelta(days=1), time.min)

    range_start = _parse_datetime(filters["start"]) if filters.get("start") else datetime.combine(date.today(), time.min)
    range_end = _parse_datetime(filters["end"]) if filters.get("end") else range_start + timedelta(days=31)

    if range_end <= range_start:
        raise ValueError("end must be after start")

    return range_start, range_end


def _next_occurrence(start_time: datetime, recurrence_type: str, interval: int) -> datetime:
    if recurrence_type == "daily":
        return start_time + timedelta(days=interval)

    if recurrence_type == "weekly":
        return start_time + timedelta(weeks=interval)

    if recurrence_type == "monthly":
        return _add_months(start_time, interval)

    return start_time


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])

    return value.replace(year=year, month=month, day=day)


def _overlaps(start_time: datetime, end_time: datetime, range_start: datetime, range_end: datetime) -> bool:
    return (
        _to_comparable_datetime(start_time) < _to_comparable_datetime(range_end)
        and _to_comparable_datetime(end_time) > _to_comparable_datetime(range_start)
    )


def _validate_recurrence(
    recurrence_type: str,
    recurrence_interval: int,
    recurrence_until: datetime | None,
    start_time: datetime,
) -> None:
    if recurrence_type not in VALID_RECURRENCE_TYPES:
        raise ValueError("recurrence_type must be one of none, daily, weekly, monthly")

    if recurrence_interval <= 0:
        raise ValueError("recurrence_interval must be greater than 0")

    if recurrence_type == "none" and recurrence_until is not None:
        raise ValueError("recurrence_until is only allowed for recurring events")

    if recurrence_until and _to_comparable_datetime(recurrence_until) < _to_comparable_datetime(start_time):
        raise ValueError("recurrence_until must be after start_time")


def _to_comparable_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")

    return value.strip()


def _optional_text(data: dict, key: str, default=None):
    value = data.get(key, default)

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")

    return value.strip()


def _required_datetime(data: dict, key: str) -> datetime:
    value = _optional_datetime(data, key)

    if value is None:
        raise ValueError(f"{key} is required")

    return value


def _optional_datetime(data: dict, key: str) -> datetime | None:
    value = data.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"{key} must be an ISO datetime string")

    return _parse_datetime(value)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_datetime(value: datetime) -> str:
    return value.isoformat()
