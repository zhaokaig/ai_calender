import tempfile
import unittest
from pathlib import Path

from app.agent.executor import execute_plan
from app.agent.schemas import CALENDAR_INTENT, SUCCESS, UPDATE_EVENT, ActionPlan, CalendarAction
from app.database import init_db
from app.event_service import create_event, get_event
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


if __name__ == "__main__":
    unittest.main()
