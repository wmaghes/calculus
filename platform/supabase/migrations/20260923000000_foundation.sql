-- =============================================================================
-- Foundation schema: organizations, users, course content, progress.
--
-- Tenancy model
--   Every user belongs to exactly one organization (solo learners get a
--   personal org of one). Every row that belongs to a person carries an
--   organization_id, and row-level security scopes reads and writes to the
--   caller's organization. Course content (tracks → modules → lessons →
--   quiz_questions) is a global catalog when tracks.organization_id is null,
--   or private to one org when it is set.
--
-- Write model
--   Learners write only their own progress and tutor history. Scores,
--   certificates, plans, seats, roles and course content are written by the
--   server with the service role key, which bypasses RLS.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
create type public.plan_type as enum ('individual', 'team', 'enterprise');
create type public.user_role as enum ('learner', 'org_admin', 'super_admin');
create type public.lesson_type as enum ('video', 'walkthrough', 'slide', 'quiz', 'exercise');
create type public.question_type as enum ('multiple_choice', 'open_ended');
create type public.progress_status as enum ('not_started', 'in_progress', 'complete');

-- ---------------------------------------------------------------------------
-- Shared trigger: keep updated_at current
-- ---------------------------------------------------------------------------
create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------
create table public.organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  plan_type   public.plan_type not null default 'individual',
  seat_count  integer not null default 1 check (seat_count >= 1),
  created_at  timestamptz not null default now()
);

-- One row per auth.users row; created by the handle_new_user trigger below.
create table public.users (
  id               uuid primary key references auth.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete restrict,
  name             text,
  email            text not null,
  role             public.user_role not null default 'learner',
  created_at       timestamptz not null default now()
);
create index users_organization_id_idx on public.users (organization_id);

-- A track is a full course, e.g. "AI for Finance Professionals".
create table public.tracks (
  id               uuid primary key default gen_random_uuid(),
  -- null = global catalog track; set = private to that organization
  organization_id  uuid references public.organizations (id) on delete cascade,
  title            text not null,
  description      text,
  target_field     text not null default 'general',
  created_at       timestamptz not null default now()
);
create index tracks_organization_id_idx on public.tracks (organization_id);

create table public.modules (
  id                 uuid primary key default gen_random_uuid(),
  track_id           uuid not null references public.tracks (id) on delete cascade,
  order_index        integer not null,
  title              text not null,
  estimated_minutes  integer not null default 10 check (estimated_minutes > 0),
  created_at         timestamptz not null default now(),
  unique (track_id, order_index) deferrable initially immediate
);

create table public.lessons (
  id            uuid primary key default gen_random_uuid(),
  module_id     uuid not null references public.modules (id) on delete cascade,
  order_index   integer not null,
  title         text not null,
  type          public.lesson_type not null,
  content_url   text,
  content_json  jsonb,
  created_at    timestamptz not null default now(),
  unique (module_id, order_index) deferrable initially immediate
);

create table public.quiz_questions (
  id              uuid primary key default gen_random_uuid(),
  lesson_id       uuid not null references public.lessons (id) on delete cascade,
  order_index     integer not null default 0,
  question_text   text not null,
  question_type   public.question_type not null,
  -- multiple_choice: [{"id": "a", "label": "..."}, ...]
  options_json    jsonb,
  -- multiple_choice: the correct option id. open_ended: the grading rubric.
  -- Never readable by learners; see the column grants below.
  correct_answer  text not null,
  created_at      timestamptz not null default now()
);
create index quiz_questions_lesson_id_idx on public.quiz_questions (lesson_id);

-- One row per lesson per user, upserted as they progress.
create table public.user_progress (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  lesson_id        uuid not null references public.lessons (id) on delete cascade,
  status           public.progress_status not null default 'not_started',
  score            numeric(5, 2) check (score between 0 and 100),
  completed_at     timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (user_id, lesson_id)
);
create index user_progress_organization_id_idx on public.user_progress (organization_id);
create trigger user_progress_updated_at before update on public.user_progress
  for each row execute function public.set_updated_at();

create table public.certificates (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  track_id         uuid not null references public.tracks (id) on delete cascade,
  issued_at        timestamptz not null default now(),
  certificate_url  text,
  unique (user_id, track_id)
);
create index certificates_organization_id_idx on public.certificates (organization_id);

-- Tutor chat history, scoped per lesson so context stays relevant.
create table public.tutor_conversations (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references public.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  lesson_id        uuid not null references public.lessons (id) on delete cascade,
  messages_json    jsonb not null default '[]'::jsonb,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (user_id, lesson_id)
);
create trigger tutor_conversations_updated_at before update on public.tutor_conversations
  for each row execute function public.set_updated_at();

-- Company rollouts: an org_admin invites an email into their organization.
-- The signup trigger consumes the invitation (see handle_new_user).
create table public.org_invitations (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  email            text not null check (email = lower(email)),
  role             public.user_role not null default 'learner' check (role <> 'super_admin'),
  invited_by       uuid references public.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  accepted_at      timestamptz
);
create unique index org_invitations_pending_email_idx
  on public.org_invitations (organization_id, email) where accepted_at is null;

-- ---------------------------------------------------------------------------
-- RLS helpers. SECURITY DEFINER so policies on public.users can call them
-- without recursing into public.users' own policies. Kept in a schema the
-- Data API does not expose.
-- ---------------------------------------------------------------------------
create schema if not exists private;
grant usage on schema private to authenticated;

create function private.current_org_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select organization_id from public.users where id = auth.uid()
$$;

create function private.is_org_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    (select role in ('org_admin', 'super_admin') from public.users where id = auth.uid()),
    false
  )
$$;

create function private.can_see_track(p_track_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.tracks t
    where t.id = p_track_id
      and (t.organization_id is null or t.organization_id = private.current_org_id())
  )
$$;

create function private.can_see_lesson(p_lesson_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.lessons l
    join public.modules m on m.id = l.module_id
    where l.id = p_lesson_id and private.can_see_track(m.track_id)
  )
$$;

revoke all on all functions in schema private from public;
grant execute on all functions in schema private to authenticated;

-- Rows owned by a user always carry that user's organization, whatever the
-- client sent. RLS then checks it against the caller's org.
create function private.stamp_organization_id()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  select organization_id into new.organization_id
  from public.users where id = new.user_id;
  return new;
end;
$$;

create trigger user_progress_stamp_org before insert on public.user_progress
  for each row execute function private.stamp_organization_id();
create trigger certificates_stamp_org before insert on public.certificates
  for each row execute function private.stamp_organization_id();
create trigger tutor_conversations_stamp_org before insert on public.tutor_conversations
  for each row execute function private.stamp_organization_id();

-- ---------------------------------------------------------------------------
-- New auth user → public.users row + organization.
--
-- A pending invitation is honoured only when the address is proven: the user
-- was invited by an admin (auth.admin.inviteUserByEmail sets invited_at) or
-- the provider already verified the email (e.g. Google). An unverified open
-- signup always lands in a fresh personal org, so nobody can join a company
-- org by typing someone else's address.
-- ---------------------------------------------------------------------------
create function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_name   text := nullif(trim(coalesce(
                     new.raw_user_meta_data ->> 'full_name',
                     new.raw_user_meta_data ->> 'name', '')), '');
  v_invite public.org_invitations;
  v_org_id uuid;
  v_role   public.user_role := 'learner';
begin
  if new.invited_at is not null or new.email_confirmed_at is not null then
    select * into v_invite
    from public.org_invitations
    where email = lower(new.email) and accepted_at is null
    order by created_at desc
    limit 1;
  end if;

  if v_invite.id is not null then
    v_org_id := v_invite.organization_id;
    v_role := v_invite.role;
    update public.org_invitations set accepted_at = now() where id = v_invite.id;
  else
    insert into public.organizations (name, plan_type, seat_count)
    values (coalesce(v_name, split_part(new.email, '@', 1)) || '''s workspace', 'individual', 1)
    returning id into v_org_id;
  end if;

  insert into public.users (id, organization_id, name, email, role)
  values (new.id, v_org_id, v_name, lower(new.email), v_role);

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- ---------------------------------------------------------------------------
-- Privileges. Start from nothing, then grant exactly what the policies need.
-- Column-level grants stop learners writing fields only the server may set
-- (role, organization_id, score, plan, seats) and reading answer keys.
-- ---------------------------------------------------------------------------
revoke all on all tables in schema public from anon, authenticated;

grant select on public.organizations to authenticated;
grant update (name) on public.organizations to authenticated;

grant select on public.users to authenticated;
grant update (name) on public.users to authenticated;

grant select on public.tracks, public.modules, public.lessons to authenticated;
grant select (id, lesson_id, order_index, question_text, question_type, options_json, created_at)
  on public.quiz_questions to authenticated;

grant select on public.user_progress to authenticated;
grant insert (user_id, lesson_id, status, completed_at) on public.user_progress to authenticated;
grant update (status, completed_at) on public.user_progress to authenticated;

grant select on public.certificates to authenticated;

grant select on public.tutor_conversations to authenticated;
grant insert (user_id, lesson_id, messages_json) on public.tutor_conversations to authenticated;
grant update (messages_json) on public.tutor_conversations to authenticated;

grant select, delete on public.org_invitations to authenticated;
grant insert (organization_id, email, role) on public.org_invitations to authenticated;

-- ---------------------------------------------------------------------------
-- Row-level security: every table, scoped by organization_id.
-- ---------------------------------------------------------------------------
alter table public.organizations       enable row level security;
alter table public.users               enable row level security;
alter table public.tracks              enable row level security;
alter table public.modules             enable row level security;
alter table public.lessons             enable row level security;
alter table public.quiz_questions      enable row level security;
alter table public.user_progress       enable row level security;
alter table public.certificates        enable row level security;
alter table public.tutor_conversations enable row level security;
alter table public.org_invitations     enable row level security;

-- organizations: members see their own org; admins may rename it.
create policy "members read own org" on public.organizations
  for select to authenticated
  using (id = private.current_org_id());
create policy "admins rename own org" on public.organizations
  for update to authenticated
  using (id = private.current_org_id() and private.is_org_admin())
  with check (id = private.current_org_id());

-- users: everyone sees themself; admins see their whole org.
create policy "read self or org as admin" on public.users
  for select to authenticated
  using (
    id = auth.uid()
    or (organization_id = private.current_org_id() and private.is_org_admin())
  );
create policy "update own profile" on public.users
  for update to authenticated
  using (id = auth.uid())
  with check (id = auth.uid());

-- content: global catalog plus the caller's org-private tracks.
create policy "read visible tracks" on public.tracks
  for select to authenticated
  using (organization_id is null or organization_id = private.current_org_id());
create policy "read modules of visible tracks" on public.modules
  for select to authenticated
  using (private.can_see_track(track_id));
create policy "read lessons of visible tracks" on public.lessons
  for select to authenticated
  using (exists (
    select 1 from public.modules m
    where m.id = module_id and private.can_see_track(m.track_id)
  ));
create policy "read questions of visible lessons" on public.quiz_questions
  for select to authenticated
  using (private.can_see_lesson(lesson_id));

-- user_progress: learners own theirs; admins read their org's.
create policy "read own progress or org as admin" on public.user_progress
  for select to authenticated
  using (
    user_id = auth.uid()
    or (organization_id = private.current_org_id() and private.is_org_admin())
  );
create policy "insert own progress" on public.user_progress
  for insert to authenticated
  with check (
    user_id = auth.uid()
    and organization_id = private.current_org_id()
    and private.can_see_lesson(lesson_id)
  );
create policy "update own progress" on public.user_progress
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid() and organization_id = private.current_org_id());

-- certificates: learners read theirs; admins read their org's. Issued by server.
create policy "read own certificates or org as admin" on public.certificates
  for select to authenticated
  using (
    user_id = auth.uid()
    or (organization_id = private.current_org_id() and private.is_org_admin())
  );

-- tutor_conversations: private to the learner, admins included.
create policy "read own tutor conversations" on public.tutor_conversations
  for select to authenticated
  using (user_id = auth.uid());
create policy "insert own tutor conversations" on public.tutor_conversations
  for insert to authenticated
  with check (
    user_id = auth.uid()
    and organization_id = private.current_org_id()
    and private.can_see_lesson(lesson_id)
  );
create policy "update own tutor conversations" on public.tutor_conversations
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- org_invitations: managed by admins of that org.
create policy "admins read org invitations" on public.org_invitations
  for select to authenticated
  using (organization_id = private.current_org_id() and private.is_org_admin());
create policy "admins create org invitations" on public.org_invitations
  for insert to authenticated
  with check (organization_id = private.current_org_id() and private.is_org_admin());
create policy "admins revoke org invitations" on public.org_invitations
  for delete to authenticated
  using (organization_id = private.current_org_id() and private.is_org_admin());
