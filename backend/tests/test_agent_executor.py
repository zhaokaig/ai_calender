import tempfile
import unittest
from pathlib import Path

from app.agent.executor import execute_plan
from app.agent.schemas import CALENDAR_INTENT, DELETE_EVENT, SUCCESS, UPDATE_EVENT, ActionPlan, CalendarAction
from app.database import init_db
from app.event_service import create_event, get_event, list_events
from app.factory import create_app


class ExecutorEventIdSelectorTest(unittest.TestCase):
    def test_update_uses_event_id_selector_for_recent_reference(self):
        app = create_app()

        with tempfile.TemporaryDirectory() as temp_dir:
            app.config["DATABASE_PATH"] = str(Path(temp_dir) / "test.sqlite")

            with app.app_context():
                init_db()
                first_event = create_event(
                    1,
                    {
                        "title": "会议",
                        "start_time": "2026-06-01T09:00:00+08:00",
                        "end_time": "2026-06-01T10:00:00+08:00",
                    },
                )
                recent_event = create_event(
                    1,
                    {
                        "title": "会议4",
                        "start_time": "2026-06-01T14:00:00+08:00",
                        "end_time": "2026-06-01T15:00:00+08:00",
                    },
                )
                plan = ActionPlan(
                    intent=CALENDAR_INTENT,
                    actions=[
                        CalendarAction(
                            type=UPDATE_EVENT,
                            arguments={
                                "selector": {"event_id": recent_event["id"]},
                                "updates": {
                                    "start_time": "2026-06-01T15:00:00+08:00",
                                    "end_time": "2026-06-01T16:00:00+08:00",
                                },
                            },
                        )
                    ],
                )

                response = execute_plan(1, plan)

                self.assertEqual(response.status, SUCCESS)
                self.assertEqual(get_event(1, first_event["id"])["start_time"], "2026-06-01T09:00:00+08:00")
                self.assertEqual(get_event(1, recent_event["id"])["start_time"], "2026-06-01T15:00:00+08:00")

    def test_delete_occurrence_scope_cancels_one_recurring_occurrence(self):
        app = create_app()

        with tempfile.TemporaryDirectory() as temp_dir:
            app.config["DATABASE_PATH"] = str(Path(temp_dir) / "test.sqlite")

            with app.app_context():
                init_db()
                create_event(
                    1,
                    {
                        "title": "课程",
                        "start_time": "2026-06-01T09:00:00+08:00",
                        "end_time": "2026-06-01T10:00:00+08:00",
                        "recurrence_type": "weekly",
                    },
                )
                plan = ActionPlan(
                    intent=CALENDAR_INTENT,
                    actions=[
                        CalendarAction(
                            type=DELETE_EVENT,
                            arguments={
                                "selector": {
                                    "scope": "occurrence",
                                    "date": "2026-06-08",
                                    "keywords": ["课程"],
                                },
                            },
                        )
                    ],
                )

                response = execute_plan(1, plan)
                events = list_events(
                    1,
                    {
                        "start": "2026-06-01T00:00:00+08:00",
                        "end": "2026-06-16T00:00:00+08:00",
                    },
                )

                self.assertEqual(response.status, SUCCESS)
                self.assertEqual([event["start_time"] for event in events], [
                    "2026-06-01T09:00:00+08:00",
                    "2026-06-15T09:00:00+08:00",
                ])

    def test_delete_future_scope_truncates_recurring_event(self):
        app = create_app()

        with tempfile.TemporaryDirectory() as temp_dir:
            app.config["DATABASE_PATH"] = str(Path(temp_dir) / "test.sqlite")

            with app.app_context():
                init_db()
                create_event(
                    1,
                    {
                        "title": "课程",
                        "start_time": "2026-06-01T09:00:00+08:00",
                        "end_time": "2026-06-01T10:00:00+08:00",
                        "recurrence_type": "weekly",
                    },
                )
                plan = ActionPlan(
                    intent=CALENDAR_INTENT,
                    actions=[
                        CalendarAction(
                            type=DELETE_EVENT,
                            arguments={
                                "selector": {
                                    "scope": "future",
                                    "date": "2026-06-15",
                                    "from": "2026-06-15T09:00:00+08:00",
                                    "keywords": ["课程"],
                                },
                            },
                        )
                    ],
                )

                response = execute_plan(1, plan)
                events = list_events(
                    1,
                    {
                        "start": "2026-06-01T00:00:00+08:00",
                        "end": "2026-06-30T00:00:00+08:00",
                    },
                )

                self.assertEqual(response.status, SUCCESS)
                self.assertEqual([event["start_time"] for event in events], [
                    "2026-06-01T09:00:00+08:00",
                    "2026-06-08T09:00:00+08:00",
                ])


if __name__ == "__main__":
    unittest.main()
