"""
agent/agent.py
=====================================================================
AnalystAgent — оркестратор.

Последовательность выполнения run_tool():
    1. PermissionChecker.check()  — проверка прав ДО запроса к БД.
    2. Если не разрешено -> запись в feedback, возврат отказа.
    3. RollbackManager.run()      — выполнение RPC с автоматическим
       откатом и уведомлением при ошибке (включая нарушение RLS).
    4. Результат (успех/ошибка) уже записан в FeedbackStore внутри
       RollbackManager — агент может опираться на историю для
       принятия решений в следующий раз (should_warn_before_retry).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.db_client import Gateway
from agent.feedback import FeedbackStore
from agent.permissions import PermissionChecker
from agent.rollback import RollbackManager
from agent.tools import AVAILABLE_TOOLS


@dataclass
class AgentToolResponse:
    success: bool
    data: Any = None
    error: str | None = None
    rolled_back: bool = False
    blocked_by_permissions: bool = False


class AnalystAgent:
    def __init__(self, gateway: Gateway, feedback_store: FeedbackStore | None = None) -> None:
        self.gateway = gateway
        self.feedback_store = feedback_store or FeedbackStore()
        self.permissions = PermissionChecker()
        self.rollback_manager = RollbackManager(gateway=gateway, feedback_store=self.feedback_store)

    def run_tool(self, tool_name: str, **params: Any) -> AgentToolResponse:
        if tool_name not in AVAILABLE_TOOLS:
            return AgentToolResponse(success=False, error=f"Неизвестный инструмент: {tool_name}")

        tool = AVAILABLE_TOOLS[tool_name]
        user_id = self.gateway.whoami() or "unknown"

        # 1. Учитываем feedback loop ДО попытки: если инструмент
        #    систематически падает — предупреждаем, но всё равно
        #    даём агенту решить (в проде здесь можно требовать
        #    подтверждения пользователя/оператора).
        warn = self.feedback_store.should_warn_before_retry(user_id, tool_name)

        # 2. Проверка прав.
        permission = self.permissions.check(self.gateway, tool_name)
        if not permission.allowed:
            self.feedback_store.record(
                user_id=user_id,
                tool_name=tool_name,
                params=params,
                success=False,
                error=f"permission_denied:{permission.reason}",
            )
            return AgentToolResponse(
                success=False,
                error=f"Доступ запрещён: {permission.reason}",
                blocked_by_permissions=True,
            )

        # 3. Выполнение с rollback-защитой.
        result = self.rollback_manager.run(rpc_name=tool.rpc_name, params=tool.build_params(**params))

        response = AgentToolResponse(
            success=result.success,
            data=result.data,
            error=result.error,
            rolled_back=result.rolled_back,
        )
        if warn and not result.success:
            response.error = (response.error or "") + " [повторяющийся сбой этого инструмента]"
        return response
