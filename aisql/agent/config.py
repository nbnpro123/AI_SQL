"""
agent/config.py
=====================================================================
Конфигурация берётся из переменных окружения (.env). Никаких секретов
в коде — см. .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    # service_role используется ТОЛЬКО для служебных задач (например,
    # создания тестовых пользователей), никогда для выполнения
    # запросов агента — иначе RLS будет обойдена.
    supabase_service_role_key: str | None
    edge_function_url: str  # URL нашего api/main.py (или Deno edge function)
    mcp_server_command: str  # команда запуска Supabase MCP Server

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass

        return cls(
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
            supabase_service_role_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
            edge_function_url=os.environ.get(
                "EDGE_FUNCTION_URL", "http://localhost:8000/agent/query"
            ),
            mcp_server_command=os.environ.get(
                "SUPABASE_MCP_COMMAND",
                "npx -y @supabase/mcp-server-supabase@latest --read-only",
            ),
        )
