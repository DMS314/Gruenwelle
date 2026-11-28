-- Grünwelle: gemeinsamer Zähler für TomTom-Verkehrsfluss (einmal im SQL-Editor ausführen)
create table if not exists public.flow_use(day date primary key, n int not null default 0);
alter table public.flow_use enable row level security;

-- zählt eine Kachel; liefert den neuen Tagesstand oder -1, wenn Tages- oder Monatslimit erreicht ist
create or replace function public.flow_hit(p_day int, p_mon int) returns int
language plpgsql security definer set search_path = public as $$
declare d date := (now() at time zone 'Europe/Berlin')::date; c int; m int;
begin
  select coalesce(sum(n), 0) into m from flow_use where day >= date_trunc('month', d)::date;
  if m >= p_mon then return -1; end if;
  insert into flow_use(day, n) values (d, 1)
  on conflict (day) do update set n = flow_use.n + 1 where flow_use.n < p_day
  returning n into c;
  return coalesce(c, -1);
end $$;

revoke execute on function public.flow_hit(int, int) from public, anon, authenticated;
grant execute on function public.flow_hit(int, int) to service_role;
