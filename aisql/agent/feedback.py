"""
agent/feedback.py
=====================================================================
Feedback loop.

FeedbackStore хранит историю попыток выполнения инструментов
(успех/ошибка/откат). Эта история используется для:
    1. Аудита (что можно синхронизировать в таблицу agent_query_log,
       см. sql/schema.sql — там та же структура на стороне БД).
    2. Простого "обучения" агента: перед повторным вызовом инструмента,
       который недавно систематически падал по одной и той же причине,
       агент может решить не пытаться снова, а сообщить пользователю.

Хранилище в этой реализации — in-memory (список), но интерфейс
специально узкий (record/history/…), чтобы его легко было заменить
на запись в agent_query_log через тот же SupabaseGateway.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Attempt:
    user_id: str
    tool_name: str
    params: dict[str, Any]
    success: bool
    error: str | None = None
    rolled_back: bool = False
    timestamp: float = field(default_factory=time.time)


class FeedbackStore:
    def __init__(self) -> None:
        self._attempts: list[Attempt] = []

    def record(
        self,
        *,
        user_id: str,
        tool_name: str,
        params: dict[str, Any],
        success: bool,
        error: str | None = None,
        rolled_back: bool = False,
    ) -> Attempt:
        attempt = Attempt(
            user_id=user_id,
            tool_name=tool_name,
            params=params,
            success=success,
            error=error,
            rolled_back=rolled_back,
        )
        self._attempts.append(attempt)
        return attempt

    def history(self, user_id: str | None = None, tool_name: str | None = None) -> list[Attempt]:
        result = self._attempts
        if user_id is not None:
            result = [a for a in result if a.user_id == user_id]
        if tool_name is not None:
            result = [a for a in result if a.tool_name == tool_name]
        return result

    def success_rate(self, user_id: str, tool_name: str) -> float | None:
        attempts = self.history(user_id=user_id, tool_name=tool_name)
        if not attempts:
            return None
        return sum(1 for a in attempts if a.success) / len(attempts)

    def recent_failures(self, user_id: str, tool_name: str, window: int = 3) -> list[Attempt]:
        attempts = self.history(user_id=user_id, tool_name=tool_name)[-window:]
        return [a for a in attempts if not a.success]

    def should_warn_before_retry(self, user_id: str, tool_name: str, window: int = 3) -> bool:
        """Если последние `window` попыток этого инструмента все неудачны — предупредить агента."""
        attempts = self.history(user_id=user_id, tool_name=tool_name)[-window:]
        return len(attempts) >= window and all(not a.success for a in attempts)
