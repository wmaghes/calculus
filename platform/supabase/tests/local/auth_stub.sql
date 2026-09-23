-- Minimal stand-in for the pieces of Supabase that the migrations touch, so
-- they can be tested against a plain Postgres (scripts/test-db.sh).
-- Never apply this to a real Supabase project: it already has all of this.
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;

create schema auth;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema public to anon, authenticated, service_role;

create table auth.users (
  id                  uuid primary key default gen_random_uuid(),
  email               text not null,
  raw_user_meta_data  jsonb not null default '{}'::jsonb,
  invited_at          timestamptz,
  email_confirmed_at  timestamptz
);

create function auth.uid() returns uuid
language sql stable
as $$
  select nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid
$$;
grant execute on function auth.uid() to anon, authenticated, service_role;

-- Supabase grants the service role everything in public by default.
alter default privileges in schema public grant all on tables to service_role;
