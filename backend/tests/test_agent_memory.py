import unittest

from app.agent.memory import clear_memory, get_recent_events, remember_events


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


if __name__ == "__main__":
    unittest.main()
