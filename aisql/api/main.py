"""
api/main.py
=====================================================================
Python-эквивалент Deno edge-функции из ТЗ.

    агент -> POST /agent/query -> сервис -> Supabase (PostgREST/RPC) -> ответ

Ключевой момент безопасности:
    Сервис НЕ использует service_role key для выполнения запроса.
    Он передаёт JWT пользователя в Supabase client, поэтому все
    ограничения RLS применяются так же, как если бы пользователь
    делал запрос сам.

Запуск:
    uvicorn api.main:app --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from agent.agent import AnalystAgent
from agent.config import Settings
from agent.db_client import SupabaseGateway
from agent.feedback import FeedbackStore
from agent.tools import AVAILABLE_TOOLS

settings = Settings.from_env()
feedback_store = FeedbackStore()

app = FastAPI(title="Agent-Analyst Edge Function (Python)")


class AgentQueryRequest(BaseModel):
    tool_name: str
    params: dict[str, Any] = {}


class AgentQueryResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    rolled_back: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/query", response_model=AgentQueryResponse)
def agent_query(
    request: AgentQueryRequest,
    authorization: str = Header(..., description="Bearer <user JWT>"),
) -> AgentQueryResponse:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Ожидается Bearer токен пользователя")
    user_jwt = authorization.removeprefix("Bearer ").strip()

    if request.tool_name not in AVAILABLE_TOOLS:
        feedback_store.record(
            user_id="unknown",
            tool_name=request.tool_name,
            params=request.params,
            success=False,
            error="tool_not_allowed",
        )
        raise HTTPException(status_code=403, detail="Инструмент не разрешён")

    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=503,
            detail="SUPABASE_URL и SUPABASE_ANON_KEY должны быть заданы в .env",
        )

    gateway = SupabaseGateway(
        url=settings.supabase_url,
        anon_key=settings.supabase_anon_key,
        user_jwt=user_jwt,
    )
    agent = AnalystAgent(gateway=gateway, feedback_store=feedback_store)
    result = agent.run_tool(request.tool_name, **request.params)

    if result.blocked_by_permissions:
        raise HTTPException(status_code=401, detail=result.error or "Доступ запрещён")

    return AgentQueryResponse(
        success=result.success,
        data=result.data,
        error=result.error,
        rolled_back=result.rolled_back,
    )
