-- =====================================================================
-- schema.sql
-- Выполнить в Supabase SQL Editor (или через `supabase db push`).
-- Создаёт:
--   1. Таблицу orders с RLS ("каждый видит только свои заказы")
--   2. Таблицу agent_query_log — журнал агента (feedback loop)
--   3. RPC-функцию get_order_statistics — единственный разрешённый
--      способ агента "выполнять запросы" к заказам (без произвольного SQL)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Таблица заказов
-- ---------------------------------------------------------------------
create table if not exists public.orders (
    id           bigint generated always as identity primary key,
    user_id      uuid not null references auth.users(id) default auth.uid(),
    product_name text not null,
    amount       numeric(12,2) not null check (amount >= 0),
    status       text not null default 'pending'
                 check (status in ('pending', 'paid', 'shipped', 'cancelled')),
    created_at   timestamptz not null default now()
);

alter table public.orders enable row level security;

-- Пользователь видит только свои заказы
create policy "orders_select_own"
    on public.orders for select
    using (auth.uid() = user_id);

-- Пользователь может создавать заказы только от своего имени
create policy "orders_insert_own"
    on public.orders for insert
    with check (auth.uid() = user_id);

-- Пользователь может изменять/удалять только свои заказы
create policy "orders_update_own"
    on public.orders for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy "orders_delete_own"
    on public.orders for delete
    using (auth.uid() = user_id);

-- service_role (используется сервером/edge-функцией) обходит RLS по умолчанию —
-- поэтому вся логика проверки прав для агента должна выполняться
-- ОТ ИМЕНИ ПОЛЬЗОВАТЕЛЯ (anon key + JWT пользователя), а не service_role.

-- ---------------------------------------------------------------------
-- 2. Журнал запросов агента (feedback loop)
-- ---------------------------------------------------------------------
create table if not exists public.agent_query_log (
    id           bigint generated always as identity primary key,
    user_id      uuid not null default auth.uid(),
    tool_name    text not null,
    params       jsonb not null default '{}'::jsonb,
    success      boolean not null,
    error_code   text,
    error_message text,
    rolled_back  boolean not null default false,
    created_at   timestamptz not null default now()
);

alter table public.agent_query_log enable row level security;

create policy "agent_log_select_own"
    on public.agent_query_log for select
    using (auth.uid() = user_id);

create policy "agent_log_insert_own"
    on public.agent_query_log for insert
    with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- 3. RPC: безопасная статистика по заказам
--    SECURITY INVOKER — функция выполняется с правами вызывающего,
--    поэтому RLS таблицы orders применяется как обычно.
-- ---------------------------------------------------------------------
create or replace function public.get_order_statistics()
returns table (
    total_orders   bigint,
    total_amount   numeric,
    avg_amount     numeric,
    by_status      jsonb
)
language sql
security invoker
set search_path = public
as $$
    select
        count(*)                                   as total_orders,
        coalesce(sum(amount), 0)                   as total_amount,
        coalesce(round(avg(amount), 2), 0)         as avg_amount,
        coalesce(jsonb_object_agg(status, cnt), '{}'::jsonb) as by_status
    from (
        select status, amount, count(*) over (partition by status) as cnt
        from public.orders
    ) s;
$$;

grant execute on function public.get_order_statistics() to authenticated;
