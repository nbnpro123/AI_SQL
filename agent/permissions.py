"""
agent/permissions.py
=====================================================================
RLS в Postgres — это последний и главный рубеж защиты: даже если
здесь есть ошибка, БД всё равно не отдаст чужие строки.

Но по ТЗ агент должен "сначала проверить права пользователя, ЗАТЕМ
выполнить запрос" — это defense-in-depth уровня приложения:
    - не тратим RPC-вызов впустую, если пользователь очевидно не
      аутентифицирован;
    - можем отсеять операции, запрещённые бизнес-правилами, которые
      не выражаются через RLS напрямую (например, "агенту нельзя
      использовать write-инструменты вообще").
"""

from __future__ import annotations

from dataclasses import dataclass

from agent.db_client import Gateway


@dataclass
class PermissionResult:
    allowed: bool
    reason: str | None = None


READ_ONLY_TOOLS = {"get_order_statistics"}
WRITE_TOOLS: set[str] = set()  # пока агенту не разрешена запись — только чтение


class PermissionChecker:
    """Проверяет права ДО обращения к БД."""

    def check(self, gateway: Gateway, tool_name: str) -> PermissionResult:
        user_id = gateway.whoami()
        if not user_id:
            return PermissionResult(allowed=False, reason="no_authenticated_user")

        if tool_name in WRITE_TOOLS:
            # В текущей версии агенту вообще не разрешена запись —
            # это решение принимается на уровне приложения, а не RLS,
            # чтобы агент не мог случайно изменить/удалить данные,
            # даже свои собственные, без явного review человеком.
            return PermissionResult(allowed=False, reason="write_tools_disabled_for_agent")

        if tool_name not in READ_ONLY_TOOLS:
            return PermissionResult(allowed=False, reason="unknown_tool")

        return PermissionResult(allowed=True)
