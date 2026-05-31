import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agent import graph
from app.agent.memory import clear_memory
from app.agent.schemas import CALENDAR_INTENT, CREATE_EVENT, SUCCESS, ActionPlan, CalendarAction, IntentResult
from app.database import init_db
from app.factory import create_app


class AgentGraphPipelineTest(unittest.TestCase):
    def setUp(self):
        clear_memory()

    def tearDown(self):
        clear_memory()

    def test_event_recognizer_receives_rewritten_calendar_text(self):
        app = create_app()
        captured_text = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            app.config["DATABASE_PATH"] = str(Path(temp_dir) / "test.sqlite")

            def fake_recognize_event_tasks(text, _timezone, _existing_events, _recent_events, _recent_turns):
                captured_text["value"] = text
                return ActionPlan(
                    intent=CALENDAR_INTENT,
                    actions=[
                        CalendarAction(
                            type=CREATE_EVENT,
                            arguments={
                                "title": "开会",
                                "start_time": "2026-06-01T10:00:00+08:00",
                                "end_time": "2026-06-01T11:00:00+08:00",
                            },
                        )
                    ],
                )

            with app.app_context():
                init_db()

                with (
                    patch.object(
                        graph,
                        "classify_intent",
                        return_value=IntentResult(intent=CALENDAR_INTENT, text="今天早上十点开会"),
                    ),
                    patch.object(graph, "recognize_event_tasks", side_effect=fake_recognize_event_tasks),
                    patch.object(graph, "generate_calendar_reply", return_value="会议已经添加完成。"),
                ):
                    response = graph.run_voice_command_graph(1, "啊 今天早上九点开会，啊不对是十点", "Asia/Shanghai")

        self.assertEqual(captured_text["value"], "今天早上十点开会")
        self.assertEqual(response.status, SUCCESS)
        self.assertEqual(response.message, "会议已经添加完成。")


if __name__ == "__main__":
    unittest.main()
