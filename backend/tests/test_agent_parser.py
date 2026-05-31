import unittest
from unittest.mock import patch

from app.factory import create_app
from app.agent import parser
from app.agent.schemas import UPDATE_EVENT


class PlannerExistingEventsTest(unittest.TestCase):
    def test_plan_calendar_actions_passes_existing_events_for_updates(self):
        app = create_app()
        app.config["OPENAI_API_KEY"] = "test-key"

        existing_events = [
            {
                "series_id": 10,
                "title": "考试",
                "start_time": "2026-05-31T16:00:00+08:00",
                "end_time": "2026-05-31T17:00:00+08:00",
            },
            {
                "series_id": 11,
                "title": "安装家具",
                "start_time": "2026-05-31T20:00:00+08:00",
                "end_time": "2026-05-31T21:00:00+08:00",
            },
        ]
        captured_payload = {}

        def fake_invoke_json(_prompt, payload):
            captured_payload.update(payload)
            return {
                "reply": None,
                "actions": [
                    {
                        "type": "update_event",
                        "confidence": 0.98,
                        "arguments": {
                            "selector": {"keywords": ["考试"], "date": "2026-05-31"},
                            "updates": {"title": "考雅思"},
                        },
                    },
                    {
                        "type": "update_event",
                        "confidence": 0.97,
                        "arguments": {
                            "selector": {"keywords": ["安装家具"], "date": "2026-05-31"},
                            "updates": {"title": "安装电动升降桌"},
                        },
                    },
                ],
            }

        with app.app_context(), patch.object(parser, "_invoke_json", side_effect=fake_invoke_json):
            plan = parser.plan_calendar_actions(
                "今天的考试是雅思考试，安装的家具是电动升降桌",
                "Asia/Shanghai",
                existing_events,
            )

        self.assertEqual([action.type for action in plan.actions], [UPDATE_EVENT, UPDATE_EVENT])
        self.assertEqual(captured_payload["existing_events"][0]["title"], "考试")
        self.assertEqual(captured_payload["existing_events"][1]["title"], "安装家具")
        self.assertEqual(plan.actions[0].arguments["updates"]["title"], "考雅思")
        self.assertEqual(plan.actions[1].arguments["updates"]["title"], "安装电动升降桌")


if __name__ == "__main__":
    unittest.main()
