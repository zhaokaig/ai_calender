import tempfile
import unittest
from pathlib import Path

from app.database import init_db
from app.event_service import (
    create_event,
    delete_event_occurrence,
    list_events,
    truncate_recurring_event,
    update_event_occurrence,
)
from app.factory import create_app


class RecurringExceptionTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app.config["DATABASE_PATH"] = str(Path(self.temp_dir.name) / "test.sqlite")

        with self.app.app_context():
            init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_delete_single_recurring_occurrence(self):
        with self.app.app_context():
            event = _create_weekly_course()

            deleted = delete_event_occurrence(1, event["id"], "2026-06-08T09:00:00+08:00")
            events = list_events(
                1,
                {
                    "start": "2026-06-01T00:00:00+08:00",
                    "end": "2026-06-23T00:00:00+08:00",
                },
            )

        self.assertEqual(deleted["start_time"], "2026-06-08T09:00:00+08:00")
        self.assertEqual([event["start_time"] for event in events], [
            "2026-06-01T09:00:00+08:00",
            "2026-06-15T09:00:00+08:00",
            "2026-06-22T09:00:00+08:00",
        ])

    def test_update_single_recurring_occurrence(self):
        with self.app.app_context():
            event = _create_weekly_course()

            updated = update_event_occurrence(
                1,
                event["id"],
                "2026-06-08T09:00:00+08:00",
                {
                    "title": "补课",
                    "start_time": "2026-06-08T15:00:00+08:00",
                    "end_time": "2026-06-08T16:30:00+08:00",
                },
            )
            events = list_events(
                1,
                {
                    "start": "2026-06-01T00:00:00+08:00",
                    "end": "2026-06-16T00:00:00+08:00",
                },
            )

        self.assertEqual(updated["title"], "补课")
        self.assertEqual(updated["occurrence_start_time"], "2026-06-08T09:00:00+08:00")
        self.assertEqual([(event["title"], event["start_time"]) for event in events], [
            ("课程", "2026-06-01T09:00:00+08:00"),
            ("补课", "2026-06-08T15:00:00+08:00"),
            ("课程", "2026-06-15T09:00:00+08:00"),
        ])

    def test_truncate_recurring_event_from_occurrence(self):
        with self.app.app_context():
            event = _create_weekly_course()

            truncated = truncate_recurring_event(1, event["id"], "2026-06-15T09:00:00+08:00")
            events = list_events(
                1,
                {
                    "start": "2026-06-01T00:00:00+08:00",
                    "end": "2026-06-30T00:00:00+08:00",
                },
            )

        self.assertEqual(truncated["recurrence_until"], "2026-06-15T08:59:59.999999+08:00")
        self.assertEqual([event["start_time"] for event in events], [
            "2026-06-01T09:00:00+08:00",
            "2026-06-08T09:00:00+08:00",
        ])


def _create_weekly_course():
    return create_event(
        1,
        {
            "title": "课程",
            "start_time": "2026-06-01T09:00:00+08:00",
            "end_time": "2026-06-01T10:00:00+08:00",
            "recurrence_type": "weekly",
            "recurrence_interval": 1,
        },
    )


if __name__ == "__main__":
    unittest.main()
