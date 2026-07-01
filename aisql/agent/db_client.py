"""
agent/db_client.py
=====================================================================
Обёртка над Supabase client.

Главный принцип безопасности:
    Мы НИКОГДА не выполняем запросы агента через service_role key.
    Вместо этого клиент создаётся с anon key + JWT конкретного
    пользователя (`postgrest.auth(user_jwt)`), поэтому PostgREST
    подставляет auth.uid() = <пользователь>, и все политики RLS
    из sql/schema.sql применяются автоматически на уровне БД —
    даже если в коде агента есть баг, обойти RLS из Python
    невозможно.

Класс написан так, чтобы его было легко подменить фейком в тестах
(см. tests/conftest.py) — сохраняется тот же публичный интерфейс:
    .rpc(name, params) -> QueryResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class QueryResult:
    success: bool
    data: Any = None
    error: str | None = None
    error_code: str | None = None


class Gateway(Protocol):
    """Интерфейс, который должны реализовывать и реальный, и фейковый gateway."""

    def rpc(self, name: str, params: dict[str, Any]) -> QueryResult: ...

    def whoami(self) -> str | None: ...


@dataclass
class SupabaseGateway:
    """
    Реальная реализация поверх supabase-py.

    Требует установленный пакет `supabase` (см. requirements.txt).
    В песочнице без сети/зависимостей класс импортируется, но не
    вызывается — для логики агента используется FakeGateway из тестов.
    """

    url: str
    anon_key: str
    user_jwt: str
    _client: Any = field(default=None, init=False, repr=False)

    def _get_client(self) -> Any:
        if self._client is None:
            from supabase import create_client  # локальный импорт: опциональная зависимость

            client = create_client(self.url, self.anon_key)
            # Подставляем JWT пользователя, чтобы PostgREST/RLS видели auth.uid()
            client.postgrest.auth(self.user_jwt)
            self._client = client
        return self._client

    def rpc(self, name: str, params: dict[str, Any]) -> QueryResult:
        try:
            client = self._get_client()
            resp = client.rpc(name, params).execute()
            return QueryResult(success=True, data=resp.data)
        except Exception as exc:  # noqa: BLE001 — нужно поймать любые ошибки Postgres/сети
            return QueryResult(
                success=False,
                error=str(exc),
                error_code=getattr(exc, "code", None),
            )

    def whoami(self) -> str | None:
        """Извлекает user_id (sub) из JWT без обращения к сети — только для логов."""
        try:
            import jwt  # PyJWT

            payload = jwt.decode(self.user_jwt, options={"verify_signature": False})
            return payload.get("sub")
        except Exception:  # noqa: BLE001
            return None
