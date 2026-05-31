import unittest

from app.text_normalizer import _should_keep_original_query


class TextNormalizerGuardTest(unittest.TestCase):
    def test_keeps_original_when_calendar_query_becomes_answer_fragment(self):
        self.assertTrue(_should_keep_original_query("今天都有什么事情？", "今天有以下事项："))

    def test_does_not_keep_original_for_normal_cleanup(self):
        self.assertFalse(_should_keep_original_query("嗯，今天下午四点开会。", "今天下午四点开会。"))


if __name__ == "__main__":
    unittest.main()
