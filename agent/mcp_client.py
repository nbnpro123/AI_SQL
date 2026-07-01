"""
agent/mcp_client.py
=====================================================================
Подключение агента к официальному Supabase MCP Server.

Supabase MCP Server запускается отдельным процессом (Node.js) и
общается по протоколу MCP через stdio. Конфигурация — в
mcp/mcp_config.json. Рекомендуется режим --read-only и/или
--project-ref, чтобы даже при компрометации агента MCP-сервер не мог
выполнять произвольные DDL/DML в других проектах.

Python-сторона использует официальный SDK `mcp` (пакет `mcp`,
https://pypi.org/project/mcp/). Импорт сделан "ленивым" и обёрнут в
try/except, чтобы модуль можно было импортировать даже в окружении
без установленного пакета (например, при юнит-тестировании остальной
логики агента без реального MCP).
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Any


class MCPNotAvailable(RuntimeError):
    """Пакет `mcp` не установлен или сервер недоступен."""


@dataclass
class MCPToolCallResult:
    success: bool
    data: Any = None
    error: str | None = None


class SupabaseMCPConnector:
    """
    Обёртка над mcp.ClientSession для запуска и вызова инструментов
    Supabase MCP Server (например, `execute_sql`, `list_tables`,
    `get_project_url`, `get_anon_key` и т.д. — полный список зависит
    от версии @supabase/mcp-server-supabase).
    """

    def __init__(self, command: str) -> None:
        self.command = command
        self._session: Any = None
        self._exit_stack: Any = None

    async def connect(self) -> None:
        try:
            from contextlib import AsyncExitStack

            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # noqa: BLE001
            raise MCPNotAvailable(
                "Пакет 'mcp' не установлен. Установите: pip install mcp"
            ) from exc

        parts = shlex.split(self.command)
        server_params = StdioServerParameters(command=parts[0], args=parts[1:])

        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def list_tools(self) -> list[str]:
        if self._session is None:
            raise MCPNotAvailable("Сначала вызовите connect()")
        response = await self._session.list_tools()
        return [tool.name for tool in response.tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolCallResult:
        if self._session is None:
            raise MCPNotAvailable("Сначала вызовите connect()")
        try:
            result = await self._session.call_tool(name, arguments)
            return MCPToolCallResult(success=not result.isError, data=result.content)
        except Exception as exc:  # noqa: BLE001
            return MCPToolCallResult(success=False, error=str(exc))

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
