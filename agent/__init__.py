"""Пакет агента-аналитика с доступом к Supabase/PostgreSQL (с RLS)."""

from agent.agent import AgentToolResponse, AnalystAgent
from agent.config import Settings
from agent.db_client import Gateway, QueryResult, SupabaseGateway
from agent.feedback import Attempt, FeedbackStore
from agent.permissions import PermissionChecker, PermissionResult
from agent.rollback import RollbackManager, RollbackResult
from agent.tools import AVAILABLE_TOOLS, Tool

__all__ = [
    "AgentToolResponse",
    "AnalystAgent",
    "Attempt",
    "AVAILABLE_TOOLS",
    "FeedbackStore",
    "Gateway",
    "PermissionChecker",
    "PermissionResult",
    "QueryResult",
    "RollbackManager",
    "RollbackResult",
    "Settings",
    "SupabaseGateway",
    "Tool",
]
