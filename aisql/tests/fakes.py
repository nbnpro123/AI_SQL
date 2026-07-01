"""
tests/fakes.py
=====================================================================
FakeGateway реализует тот же интерфейс, что и agent.db_client.Gateway
(rpc/whoami), но хранит данные в памяти и вручную симулирует правила
RLS из sql/schema.sql: "select ... using (auth.uid() = user_id)".

Это позволяет тестировать ВСЮ логику агента (права, feedback,
rollback) без сети и без реального Supabase-проекта, при этом тесты
проверяют именно то поведение, которое должна обеспечивать RLS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.db_client import QueryResult


@dataclass
class FakeOrder:
    id: int
    user_id: str
    amount: float
    status: str = "pending"


class FakeDatabase:
    """Общее "хранилище" (аналог Postgres) для нескольких FakeGateway/пользователей."""

    def __init__(self) -> None:
        self.orders: list[FakeOrder] = []
        self._next_id = 1

    def seed_order(self, user_id: str, amount: float, status: str = "pending") -> FakeOrder:
        order = FakeOrder(id=self._next_id, user_id=user_id, amount=amount, status=status)
        self._next_id += 1
        self.orders.append(order)
        return order

    def orders_for(self, user_id: str) -> list[FakeOrder]:
        # Это и есть симуляция RLS-политики "orders_select_own"
        return [o for o in self.orders if o.user_id == user_id]


@dataclass
class FakeGateway:
    """
    Симулирует SupabaseGateway для одного аутентифицированного
    (или неаутентифицированного, если user_id=None) пользователя.
    """

    db: FakeDatabase
    user_id: str | None
    # Если True — следующий rpc-вызов симулирует попытку обратиться
    # к чужим данным и должен быть заблокирован "RLS" (42501).
    simulate_rls_violation: bool = False
    force_error: str | None = None

    def whoami(self) -> str | None:
        return self.user_id

    def rpc(self, name: str, params: dict[str, Any]) -> QueryResult:
        if self.user_id is None:
            return QueryResult(success=False, error="not authenticated", error_code="42501")

        if self.force_error is not None:
            return QueryResult(success=False, error=self.force_error, error_code="XX000")

        if self.simulate_rls_violation:
            return QueryResult(
                success=False,
                error="new row violates row-level security policy for table orders",
                error_code="42501",
            )

        if name == "get_order_statistics":
            visible = self.db.orders_for(self.user_id)  # RLS: только свои строки
            total = len(visible)
            total_amount = sum(o.amount for o in visible)
            avg_amount = round(total_amount / total, 2) if total else 0
            by_status: dict[str, int] = {}
            for o in visible:
                by_status[o.status] = by_status.get(o.status, 0) + 1
            return QueryResult(
                success=True,
                data={
                    "total_orders": total,
                    "total_amount": total_amount,
                    "avg_amount": avg_amount,
                    "by_status": by_status,
                },
            )

        return QueryResult(success=False, error=f"unknown rpc: {name}", error_code="42883")
