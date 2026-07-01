import unittest

from agent.agent import AnalystAgent
from tests.fakes import FakeDatabase, FakeGateway


class TestAgentTools(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeDatabase()
        self.db.seed_order(user_id="user-A", amount=100, status="paid")
        self.db.seed_order(user_id="user-A", amount=50, status="shipped")

    def test_successful_statistics_call(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A")
        agent = AnalystAgent(gateway=gateway)

        response = agent.run_tool("get_order_statistics")

        self.assertTrue(response.success)
        self.assertEqual(response.data["total_orders"], 2)
        self.assertFalse(response.rolled_back)
        self.assertFalse(response.blocked_by_permissions)

    def test_unknown_tool_rejected(self) -> None:
        gateway = FakeGateway(db=self.db, user_id="user-A")
        agent = AnalystAgent(gateway=gateway)

        response = agent.run_tool("delete_all_orders")

        self.assertFalse(response.success)
        self.assertIn("Неизвестный", response.error)

    def test_unauthenticated_user_blocked_by_permissions(self) -> None:
        gateway = FakeGateway(db=self.db, user_id=None)
        agent = AnalystAgent(gateway=gateway)

        response = agent.run_tool("get_order_statistics")

        self.assertFalse(response.success)
        self.assertTrue(response.blocked_by_permissions)

    def test_write_tool_disabled_even_if_requested(self) -> None:
        # Инструмента для записи в AVAILABLE_TOOLS нет вовсе — проверяем,
        # что агент не даст его вызвать под видом произвольного имени.
        gateway = FakeGateway(db=self.db, user_id="user-A")
        agent = AnalystAgent(gateway=gateway)

        response = agent.run_tool("update_order")

        self.assertFalse(response.success)


if __name__ == "__main__":
    unittest.main()
