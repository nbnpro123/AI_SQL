import unittest

from tests.fakes import FakeDatabase, FakeGateway


class TestRLS(unittest.TestCase):
    def setUp(self) -> None:
        self.db = FakeDatabase()
        self.db.seed_order(user_id="user-A", amount=100, status="paid")
        self.db.seed_order(user_id="user-A", amount=50, status="pending")
        self.db.seed_order(user_id="user-B", amount=999, status="paid")

    def test_user_sees_only_own_orders(self) -> None:
        gw_a = FakeGateway(db=self.db, user_id="user-A")
        result = gw_a.rpc("get_order_statistics", {})
        self.assertTrue(result.success)
        self.assertEqual(result.data["total_orders"], 2)
        self.assertEqual(result.data["total_amount"], 150)

    def test_other_user_does_not_leak_data(self) -> None:
        gw_b = FakeGateway(db=self.db, user_id="user-B")
        result = gw_b.rpc("get_order_statistics", {})
        self.assertTrue(result.success)
        self.assertEqual(result.data["total_orders"], 1)
        self.assertEqual(result.data["total_amount"], 999)

    def test_unauthenticated_user_is_blocked(self) -> None:
        gw_anon = FakeGateway(db=self.db, user_id=None)
        result = gw_anon.rpc("get_order_statistics", {})
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "42501")

    def test_no_cross_user_leakage_across_many_users(self) -> None:
        for i in range(5):
            self.db.seed_order(user_id=f"user-{i}", amount=i * 10)
        for i in range(5):
            gw = FakeGateway(db=self.db, user_id=f"user-{i}")
            result = gw.rpc("get_order_statistics", {})
            self.assertEqual(result.data["total_orders"], 1)
            self.assertEqual(result.data["total_amount"], i * 10)


if __name__ == "__main__":
    unittest.main()
