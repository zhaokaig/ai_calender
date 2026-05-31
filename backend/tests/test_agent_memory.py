import unittest

from app.agent.memory import clear_memory, get_recent_events, remember_events
from app.agent.memory import get_recent_turns, remember_turn
from app.agent.schemas import CALENDAR_INTENT, CREATE_EVENT, SUCCESS, AgentResponse, CalendarAction


class AgentMemoryTest(unittest.TestCase):
    def tearDown(self):
        clear_memory()

    def test_remember_events_keeps_latest_event_first(self):
        remember_events(
            1,
            [
                {
                    "id": 1,
                    "title": "会议1",
                    "start_time": "2026-06-01T09:00:00+08:00",
                    "end_time": "2026-06-01T10:00:00+08:00",
                }
            ],
        )
        remember_events(
            1,
            [
                {
                    "id": 4,
                    "title": "会议4",
                    "start_time": "2026-06-01T14:00:00+08:00",
                    "end_time": "2026-06-01T15:00:00+08:00",
                }
            ],
        )

        recent_events = get_recent_events(1)

        self.assertEqual([event["id"] for event in recent_events], [4, 1])
        self.assertEqual(recent_events[0]["title"], "会议4")

    def test_remember_events_deduplicates_updated_events(self):
        remember_events(1, [{"id": 4, "title": "会议4"}])
        remember_events(1, [{"id": 4, "title": "客户会议"}])

        recent_events = get_recent_events(1)

        self.assertEqual(len(recent_events), 1)
        self.assertEqual(recent_events[0]["title"], "客户会议")

    def test_remember_turn_stores_user_text_actions_and_events(self):
        response = AgentResponse(
            intent=CALENDAR_INTENT,
            status=SUCCESS,
            message="已创建日程：会议4。",
            actions=[
                CalendarAction(
                    type=CREATE_EVENT,
                    arguments={
                        "title": "会议4",
                        "start_time": "2026-06-01T14:00:00+08:00",
                        "end_time": "2026-06-01T15:00:00+08:00",
                    },
                )
            ],
            events=[
                {
                    "id": 4,
                    "title": "会议4",
                    "start_time": "2026-06-01T14:00:00+08:00",
                    "end_time": "2026-06-01T15:00:00+08:00",
                }
            ],
        )

        remember_turn(1, "添加一个会议4", response)
        recent_turns = get_recent_turns(1)

        self.assertEqual(recent_turns[0]["user_text"], "添加一个会议4")
        self.assertEqual(recent_turns[0]["assistant_message"], "已创建日程：会议4。")
        self.assertEqual(recent_turns[0]["actions"][0]["type"], CREATE_EVENT)
        self.assertEqual(recent_turns[0]["events"][0]["id"], 4)


if __name__ == "__main__":
    unittest.main()
