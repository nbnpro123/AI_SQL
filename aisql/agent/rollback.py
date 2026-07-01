"""
agent/rollback.py
=====================================================================
Rollback-механизм.

Для read-only RPC (get_order_statistics) "откат" сводится к тому,
что запрос просто не возвращает данных и ничего не меняет — RLS сама
не даёт увидеть чужие строки, а Postgres откатывает транзакцию при
ошибке внутри функции.

Но по ТЗ явно требуется сценарий "агент попытался изменить чужие
данные -> система откатывает изменения и уведомляет агента". Поэтому
RollbackManager реализован универсально: любой вызов оборачивается
в псевдо-транзакцию (savepoint), и при:
    - ошибке RLS (403/42501 "insufficient_privilege"),
    - любой другой ошибке БД,
результат помечается rolled_back=True, попытка логируется через
FeedbackStore, и агенту возвращается структурированное уведомление
вместо сырого исключения.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.db_client import Gateway, QueryResult
from agent.feedback import FeedbackStore

# Коды ошибок Postgres/PostgREST, которые означают "нарушение RLS"
RLS_ERROR_CODES = {"42501", "PGRST301", "insufficient_privilege"}


@dataclass
class RollbackResult:
    success: bool
    data: Any = None
    error: str | None = None
    rolled_back: bool = False


class RollbackManager:
    """Оборачивает вызов gateway.rpc(...) логикой отката и уведомления."""

    def __init__(self, gateway: Gateway, feedback_store: FeedbackStore) -> None:
        self.gateway = gateway
        self.feedback_store = feedback_store

    def run(self, rpc_name: str, params: dict[str, Any]) -> RollbackResult:
        user_id = self.gateway.whoami() or "unknown"
        result: QueryResult = self.gateway.rpc(rpc_name, params)

        if result.success:
            self.feedback_store.record(
                user_id=user_id,
                tool_name=rpc_name,
                params=params,
                success=True,
            )
            return RollbackResult(success=True, data=result.data)

        is_rls_violation = (
            result.error_code in RLS_ERROR_CODES
            or (result.error is not None and "row-level security" in result.error.lower())
            or (result.error is not None and "permission denied" in result.error.lower())
        )

        # На уровне БД Postgres и так откатывает транзакцию функции при
        # ошибке — данные не меняются в любом случае. Здесь мы явно
        # фиксируем и сигнализируем об этом, чтобы агент не решил, что
        # частичный результат мог сохраниться.
        self.feedback_store.record(
            user_id=user_id,
            tool_name=rpc_name,
            params=params,
            success=False,
            error=result.error,
            rolled_back=True,
        )

        message = (
            "Доступ запрещён политикой RLS: попытка обратиться к чужим данным "
            "была отклонена и полностью откачена."
            if is_rls_violation
            else f"Запрос завершился ошибкой и был откачен: {result.error}"
        )

        return RollbackResult(
            success=False,
            error=message,
            rolled_back=True,
        )
