import unittest

from agent.feedback import FeedbackStore


class TestFeedbackLoop(unittest.TestCase):
    def test_records_and_filters_history(self) -> None:
        store = FeedbackStore()
        store.record(user_id="u1", tool_name="get_order_statistics", params={}, success=True)
        store.record(user_id="u1", tool_name="get_order_statistics", params={}, success=False, error="boom")
        store.record(user_id="u2", tool_name="get_order_statistics", params={}, success=True)

        self.assertEqual(len(store.history(user_id="u1")), 2)
        self.assertEqual(len(store.history(user_id="u2")), 1)

    def test_success_rate(self) -> None:
        store = FeedbackStore()
        store.record(user_id="u1", tool_name="t", params={}, success=True)
        store.record(user_id="u1", tool_name="t", params={}, success=True)
        store.record(user_id="u1", tool_name="t", params={}, success=False)

        rate = store.success_rate("u1", "t")
        self.assertAlmostEqual(rate, 2 / 3)

    def test_success_rate_none_when_no_history(self) -> None:
        store = FeedbackStore()
        self.assertIsNone(store.success_rate("nobody", "nothing"))

    def test_should_warn_before_retry_after_repeated_failures(self) -> None:
        store = FeedbackStore()
        for _ in range(3):
            store.record(user_id="u1", tool_name="t", params={}, success=False, error="err")

        self.assertTrue(store.should_warn_before_retry("u1", "t", window=3))

    def test_should_not_warn_if_recent_attempt_succeeded(self) -> None:
        store = FeedbackStore()
        store.record(user_id="u1", tool_name="t", params={}, success=False)
        store.record(user_id="u1", tool_name="t", params={}, success=False)
        store.record(user_id="u1", tool_name="t", params={}, success=True)

        self.assertFalse(store.should_warn_before_retry("u1", "t", window=3))


if __name__ == "__main__":
    unittest.main()
