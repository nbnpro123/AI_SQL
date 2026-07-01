"""Общие фикстуры pytest (см. tests/fakes.py)."""

from __future__ import annotations

import pytest

from tests.fakes import FakeDatabase, FakeGateway


@pytest.fixture
def fake_db() -> FakeDatabase:
    db = FakeDatabase()
    db.seed_order(user_id="user-A", amount=100, status="paid")
    db.seed_order(user_id="user-A", amount=50, status="pending")
    db.seed_order(user_id="user-B", amount=999, status="paid")
    return db


@pytest.fixture
def gateway_user_a(fake_db: FakeDatabase) -> FakeGateway:
    return FakeGateway(db=fake_db, user_id="user-A")
