"""
agent/tools.py
=====================================================================
Инструменты ("skills") агента. У каждого инструмента:
    - name        — имя, под которым его вызывает LLM/агент;
    - rpc_name    — соответствующая RPC-функция в Supabase;
    - описание    — для регистрации в system prompt / MCP tool list.

Инструмент НЕ обращается к БД напрямую — он лишь описывает, ЧТО
нужно выполнить. Реальный вызов, проверку прав и rollback делает
agent.py, используя PermissionChecker и RollbackManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    rpc_name: str
    description: str

    def build_params(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)


GET_ORDER_STATISTICS = Tool(
    name="get_order_statistics",
    rpc_name="get_order_statistics",
    description=(
        "Получить статистику по заказам ТЕКУЩЕГО пользователя: "
        "количество заказов, суммарная и средняя сумма, разбивка по статусам. "
        "Работает только с заказами, видимыми пользователю по RLS."
    ),
)

AVAILABLE_TOOLS: dict[str, Tool] = {
    GET_ORDER_STATISTICS.name: GET_ORDER_STATISTICS,
}
