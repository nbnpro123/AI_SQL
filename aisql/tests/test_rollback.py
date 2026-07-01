import unittest

from agent.feedback import FeedbackStore
from agent.rollback import RollbackManager
from tests.fakes import FakeDatabase, FakeGateway


class TestRollback(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeDatabase()
        self.db.seed_order(user_id="user-A", amount=10)

    def test_successful_query_not_rolled_back(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A")
        store = FeedbackStore()
        manager = RollbackManager(gateway=gateway, feedback_store=store)

        result = manager.run("get_order_statistics", {})

        self.assertTrue(result.success)
        self.assertFalse(result.rolled_back)

    def test_rls_violation_triggers_rollback_and_notification(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A", simulate_rls_violation=True)
        store = FeedbackStore()
        manager = RollbackManager(gateway=gateway, feedback_store=store)

        result = manager.run("get_order_statistics", {})

        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertIn("RLS", result.error)

    def test_rollback_is_logged_in_feedback_store(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A", simulate_rls_violation=True)
        store = FeedbackStore()
        manager = RollbackManager(gateway=gateway, feedback_store=store)

        manager.run("get_order_statistics", {})

        history = store.history(user_id="user-A", tool_name="get_order_statistics")
        self.assertEqual(len(history), 1)
        self.assertFalse(history[0].success)
        self.assertTrue(history[0].rolled_back)

    def test_generic_db_error_also_rolled_back(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A", force_error="connection reset")
        store = FeedbackStore()
        manager = RollbackManager(gateway=gateway, feedback_store=store)

        result = manager.run("get_order_statistics", {})

        self.assertFalse(result.success)
        self.assertTrue(result.rolled_back)
        self.assertIn("connection reset", result.error)


if __name__ == "__main__":
    unittest.main()
