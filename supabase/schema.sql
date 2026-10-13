-- Kozquloq dashboard feed. Apply via the Supabase SQL editor or `supabase db push`.
-- The web app reads the newest row; the audit pipeline inserts one row per report.

create table if not exists reports (
  id bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  payload jsonb not null
);

-- Dashboards are public read; writes need the service role key.
alter table reports enable row level security;

create policy "reports are publicly readable"
  on reports for select
  using (true);
