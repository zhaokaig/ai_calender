import unittest
from datetime import timedelta
from unittest.mock import patch

from app.factory import create_app
from app.agent import parser
from app.agent.schemas import QUERY_EVENTS, UPDATE_EVENT


class PlannerExistingEventsTest(unittest.TestCase):
    def test_classify_intent_returns_rewritten_calendar_text(self):
        app = create_app()
        app.config["OPENAI_API_KEY"] = "test-key"

        def fake_invoke_json(_prompt, _payload):
            return {"intent": "calendar", "text": "今天早上十点开会"}

        with app.app_context(), patch.object(parser, "_invoke_json", side_effect=fake_invoke_json):
            result = parser.classify_intent("啊 今天早上九点开会，啊不对是十点", "Asia/Shanghai")

        self.assertEqual(result.intent, "calendar")
        self.assertEqual(result.text, "今天早上十点开会")

    def test_plan_calendar_actions_falls_back_for_today_query_answer_fragment(self):
        app = create_app()
        app.config["OPENAI_API_KEY"] = "test-key"

        def fake_invoke_json(_prompt, _payload):
            return {"reply": None, "actions": []}

        with app.app_context(), patch.object(parser, "_invoke_json", side_effect=fake_invoke_json):
            plan = parser.plan_calendar_actions("今天有以下事项：", "Asia/Shanghai")

        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].type, QUERY_EVENTS)
        self.assertIn("date", plan.actions[0].arguments)
        self.assertEqual(plan.actions[0].arguments["period_label"], "今天")

    def test_plan_calendar_actions_falls_back_for_week_query(self):
        app = create_app()
        app.config["OPENAI_API_KEY"] = "test-key"

        def fake_invoke_json(_prompt, _payload):
            return {"reply": None, "actions": []}

        with app.app_context(), patch.object(parser, "_invoke_json", side_effect=fake_invoke_json):
            plan = parser.plan_calendar_actions("这周有什么事要做", "Asia/Shanghai")

        start_time = parser.datetime.fromisoformat(plan.actions[0].arguments["start"])
        end_time = parser.datetime.fromisoformat(plan.actions[0].arguments["end"])

        self.assertEqual(plan.actions[0].type, QUERY_EVENTS)
        self.assertEqual(plan.actions[0].arguments["period_label"], "这周")
        self.assertEqual(start_time.utcoffset(), timedelta(hours=8))
        self.assertEqual((end_time - start_time).days, 7)
        self.assertEqual(start_time.weekday(), 0)

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

    def test_plan_calendar_actions_passes_recent_events_for_references(self):
        app = create_app()
        app.config["OPENAI_API_KEY"] = "test-key"
        captured_payload = {}

        def fake_invoke_json(_prompt, payload):
            captured_payload.update(payload)
            return {
                "reply": None,
                "actions": [
                    {
                        "type": "update_event",
                        "confidence": 0.99,
                        "arguments": {
                            "selector": {"event_id": 4},
                            "updates": {
                                "start_time": "2026-06-01T15:00:00+08:00",
                                "end_time": "2026-06-01T16:00:00+08:00",
                            },
                        },
                    }
                ],
            }

        with app.app_context(), patch.object(parser, "_invoke_json", side_effect=fake_invoke_json):
            plan = parser.plan_calendar_actions(
                "把我刚刚说的会议时间改到3点",
                "Asia/Shanghai",
                existing_events=[
                    {"id": 1, "title": "会议1"},
                    {"id": 2, "title": "会议2"},
                    {"id": 3, "title": "会议3"},
                    {"id": 4, "title": "会议4"},
                ],
                recent_events=[
                    {
                        "id": 4,
                        "title": "会议4",
                        "start_time": "2026-06-01T14:00:00+08:00",
                        "end_time": "2026-06-01T15:00:00+08:00",
                    }
                ],
                recent_turns=[
                    {
                        "user_text": "添加一个会议4",
                        "assistant_message": "已创建日程：会议4。",
                        "status": "success",
                        "intent": "calendar",
                        "actions": [{"type": "create_event", "arguments": {"title": "会议4"}}],
                        "events": [{"id": 4, "title": "会议4"}],
                    }
                ],
            )

        self.assertEqual(captured_payload["recent_events"][0]["id"], 4)
        self.assertEqual(captured_payload["recent_events"][0]["title"], "会议4")
        self.assertEqual(captured_payload["recent_turns"][0]["user_text"], "添加一个会议4")
        self.assertEqual(captured_payload["recent_turns"][0]["events"][0]["id"], 4)
        self.assertEqual(plan.actions[0].arguments["selector"]["event_id"], 4)


if __name__ == "__main__":
    unittest.main()
