# Агент-аналитик с доступом к БД (Supabase + Python)

Полностью на Python: агент, edge-функция (FastAPI), проверка прав,
feedback loop, rollback, интеграция с Supabase MCP Server.

## Структура проекта

```
.
├── agent/                  # Ядро агента
│   ├── agent.py            # AnalystAgent — оркестратор
│   ├── config.py           # Настройки из .env
│   ├── db_client.py        # SupabaseGateway (anon key + JWT)
│   ├── feedback.py         # FeedbackStore — журнал попыток
│   ├── mcp_client.py       # Клиент Supabase MCP Server
│   ├── permissions.py      # PermissionChecker
│   ├── rollback.py         # RollbackManager
│   └── tools.py            # Белый список инструментов
├── api/
│   └── main.py             # FastAPI edge-функция
├── sql/
│   └── schema.sql          # orders + RLS, agent_query_log, RPC
├── mcp/
│   └── mcp_config.json     # Конфиг @supabase/mcp-server-supabase
├── tests/                  # 17 unit-тестов (fake-БД, без сети)
├── .env.example
├── requirements.txt
└── pytest.ini
```

## Архитектура

```
[LLM/агент] --tool call--> AnalystAgent.run_tool()
                                │
                    1) PermissionChecker  (права ДО запроса)
                                │
                    2) RollbackManager.run()
                                │
                    3) SupabaseGateway.rpc()  -- anon key + JWT пользователя
                                │
                          PostgREST -> Postgres (RLS применяется автоматически)
                                │
                    4) FeedbackStore.record()  (успех/ошибка/rollback)
```

Отдельно: `api/main.py` — HTTP-сервис (аналог Deno edge-функции),
принимает запрос агента, проверяет Bearer-токен пользователя,
вызывает тот же путь `PermissionChecker -> RollbackManager -> Gateway`.

## Безопасность

- Агент **никогда** не использует `service_role` key.
- `SupabaseGateway` создаётся с `anon` key + JWT пользователя — RLS
  из `sql/schema.sql` применяется на уровне БД.
- `PermissionChecker` отсекает неаутентифицированные запросы и write-инструменты.
- Произвольный SQL запрещён: только RPC из белого списка (`AVAILABLE_TOOLS`).

## Быстрый старт

```bash
# 1. Зависимости
pip install -r requirements.txt

# 2. Переменные окружения
cp .env.example .env   # заполнить SUPABASE_URL / SUPABASE_ANON_KEY

# 3. Схема БД
#    supabase db push  — или выполнить sql/schema.sql в SQL Editor

# 4. Edge-функция (FastAPI)
python -m uvicorn api.main:app --reload

# 5. Проверка
curl http://localhost:8000/health

# 6. Тесты (не требуют Supabase)
python -m unittest discover -s tests -v
# или
pytest tests/ -v
```

## Подключение через MCP

```bash
export SUPABASE_ACCESS_TOKEN=<personal access token из Supabase Dashboard>
npx -y @supabase/mcp-server-supabase@latest --read-only --project-ref=<ref>
```

Конфиг для Cursor/Claude Desktop: `mcp/mcp_config.json`.

## Пример использования агента

```python
from agent import AnalystAgent, SupabaseGateway

gateway = SupabaseGateway(
    url="https://xxxx.supabase.co",
    anon_key="...",
    user_jwt="<JWT после логина пользователя>",
)
agent = AnalystAgent(gateway=gateway)

response = agent.run_tool("get_order_statistics")
print(response.success, response.data, response.rolled_back)
```

## Тесты

| Файл | Что проверяет |
|---|---|
| `test_rls.py` | RLS: пользователь видит только свои заказы |
| `test_agent_tools.py` | Известные/неизвестные инструменты, права |
| `test_feedback_loop.py` | История, success rate, предупреждения |
| `test_rollback.py` | RLS-нарушение и ошибки БД → rollback |

Тесты используют `tests/fakes.py` — in-memory «БД» с симуляцией RLS.
