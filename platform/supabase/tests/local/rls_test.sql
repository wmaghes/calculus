-- Row-level security tests for the foundation migration.
-- Run with scripts/test-db.sh. Any failed check raises and stops the run.
\set ON_ERROR_STOP on
\set QUIET on
\o /dev/null

create function pg_temp.check(ok boolean, label text) returns void
language plpgsql as $$
begin
  if ok is not true then raise exception 'FAIL: %', label; end if;
  raise notice 'ok   %', label;
end $$;

-- Runs a statement as the given user and passes only if Postgres refuses it.
-- A null uid runs it as the anon role, like a signed-out visitor.
create function pg_temp.check_denied(uid uuid, stmt text, label text) returns void
language plpgsql as $$
begin
  perform set_config('request.jwt.claims', json_build_object('sub', uid)::text, true);
  if uid is null then set local role anon; else set local role authenticated; end if;
  begin
    execute stmt;
  exception when insufficient_privilege or check_violation then
    reset role;
    raise notice 'ok   %', label;
    return;
  end;
  reset role;
  raise exception 'FAIL: % (statement was allowed)', label;
end $$;

-- ---- fixtures (as superuser, like the service role) ------------------------
\set a '00000000-0000-0000-0000-00000000000a'
\set b '00000000-0000-0000-0000-00000000000b'
\set c '00000000-0000-0000-0000-00000000000c'
\set d '00000000-0000-0000-0000-00000000000d'

insert into public.organizations (id, name, plan_type, seat_count)
values ('11111111-0000-0000-0000-000000000001', 'Acme Bank', 'team', 25);
insert into public.org_invitations (organization_id, email, role)
values ('11111111-0000-0000-0000-000000000001', 'bea@acme.com', 'org_admin');

-- a: open signup, unverified -> personal org
insert into auth.users (id, email, raw_user_meta_data)
values (:'a', 'Ana@Example.com', '{"full_name": "Ana Solo"}');
-- b: invited by an admin -> joins Acme as org_admin
insert into auth.users (id, email, invited_at) values (:'b', 'bea@acme.com', now());

select pg_temp.check(
  (select role = 'learner' and email = 'ana@example.com' from public.users where id = :'a'),
  'open signup creates a learner with a lower-cased email');
select pg_temp.check(
  (select o.plan_type = 'individual' and o.name = 'Ana Solo''s workspace'
     from public.users u join public.organizations o on o.id = u.organization_id
    where u.id = :'a'),
  'open signup gets a personal org');
select organization_id as a_org from public.users where id = :'a' \gset
select pg_temp.check(
  (select role = 'org_admin' and organization_id = '11111111-0000-0000-0000-000000000001'
     from public.users where id = :'b'),
  'invited user joins the inviting org with the invited role');
select pg_temp.check(
  (select accepted_at is not null from public.org_invitations where email = 'bea@acme.com'),
  'invitation is marked accepted');

-- content: one global track, one private to Acme
insert into public.tracks (id, organization_id, title, target_field) values
  ('22222222-0000-0000-0000-000000000001', null, 'AI for Finance Professionals', 'finance'),
  ('22222222-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000001', 'Acme internal', 'finance');
insert into public.modules (id, track_id, order_index, title) values
  ('33333333-0000-0000-0000-000000000001', '22222222-0000-0000-0000-000000000001', 1, 'What an LLM is'),
  ('33333333-0000-0000-0000-000000000002', '22222222-0000-0000-0000-000000000002', 1, 'Acme policy');
insert into public.lessons (id, module_id, order_index, title, type) values
  ('44444444-0000-0000-0000-000000000001', '33333333-0000-0000-0000-000000000001', 1, 'Quiz', 'quiz'),
  ('44444444-0000-0000-0000-000000000002', '33333333-0000-0000-0000-000000000002', 1, 'Policy', 'slide');
insert into public.quiz_questions (lesson_id, question_text, question_type, options_json, correct_answer)
values ('44444444-0000-0000-0000-000000000001', 'What is a token?', 'multiple_choice',
        '[{"id":"a","label":"A chunk of text"},{"id":"b","label":"A password"}]', 'a');

-- ---- as bea (Acme org_admin) ------------------------------------------------
begin;
select set_config('request.jwt.claims', json_build_object('sub', :'b')::text, true);
set local role authenticated;
insert into public.org_invitations (organization_id, email)
values ('11111111-0000-0000-0000-000000000001', 'cal@acme.com'),
       ('11111111-0000-0000-0000-000000000001', 'eve@acme.com');
select pg_temp.check((select count(*) = 2 from public.tracks), 'org member sees global + own-org tracks');
commit;

select pg_temp.check_denied(:'b',
  format($$insert into public.org_invitations (organization_id, email) values (%L, 'x@x.com')$$, :'a_org'),
  'admin cannot invite into another org');

-- c: invited learner; d: attacker doing an unverified open signup as eve@acme.com
insert into auth.users (id, email, invited_at) values (:'c', 'cal@acme.com', now());
insert into auth.users (id, email) values (:'d', 'eve@acme.com');
select pg_temp.check(
  (select organization_id = '11111111-0000-0000-0000-000000000001' from public.users where id = :'c'),
  'invited learner joins Acme');
select pg_temp.check(
  (select organization_id <> '11111111-0000-0000-0000-000000000001' from public.users where id = :'d'),
  'unverified signup with an invited address does NOT join the org');
select pg_temp.check(
  (select accepted_at is null from public.org_invitations where email = 'eve@acme.com'),
  'unverified signup does not consume the invitation');

-- ---- as ana (solo learner) --------------------------------------------------
begin;
select set_config('request.jwt.claims', json_build_object('sub', :'a')::text, true);
set local role authenticated;
select pg_temp.check((select count(*) = 1 from public.tracks), 'solo learner sees only the global track');
select pg_temp.check((select count(*) = 1 from public.users), 'learner sees only their own user row');
select pg_temp.check((select count(*) = 1 from public.organizations), 'learner sees only their own org');
select pg_temp.check((select count(*) = 0 from public.org_invitations), 'learner sees no invitations');
commit;

select pg_temp.check_denied(:'a',
  $$insert into public.user_progress (user_id, lesson_id, status)
    values ('00000000-0000-0000-0000-00000000000a', '44444444-0000-0000-0000-000000000002', 'in_progress')$$,
  'learner cannot record progress on another org''s private lesson');

-- ---- as cal (Acme learner) --------------------------------------------------
begin;
select set_config('request.jwt.claims', json_build_object('sub', :'c')::text, true);
set local role authenticated;
insert into public.user_progress (user_id, lesson_id, status)
values (:'c', '44444444-0000-0000-0000-000000000001', 'in_progress');
insert into public.user_progress (user_id, lesson_id, status)
values (:'c', '44444444-0000-0000-0000-000000000001', 'complete')
on conflict (user_id, lesson_id) do update set status = excluded.status, completed_at = now();
insert into public.tutor_conversations (user_id, lesson_id, messages_json)
values (:'c', '44444444-0000-0000-0000-000000000001', '[{"role":"user","content":"hi"}]');
select pg_temp.check(
  (select status = 'complete' and organization_id = '11111111-0000-0000-0000-000000000001'
     from public.user_progress where user_id = :'c'),
  'learner upserts own progress; organization_id is stamped server-side');
select pg_temp.check(
  (select count(*) = 1 from public.quiz_questions),
  'learner can read quiz questions');
commit;

select pg_temp.check_denied(:'c', $$select correct_answer from public.quiz_questions$$,
  'learner cannot read answer keys');
select pg_temp.check_denied(:'c', $$update public.user_progress set score = 100$$,
  'learner cannot set their own score');
select pg_temp.check_denied(:'c', $$update public.users set role = 'org_admin' where id = auth.uid()$$,
  'learner cannot promote themself');
select pg_temp.check_denied(:'c', $$update public.organizations set seat_count = 999$$,
  'learner cannot change seats');
select pg_temp.check_denied(:'c',
  $$insert into public.user_progress (user_id, lesson_id, status)
    values ('00000000-0000-0000-0000-00000000000a', '44444444-0000-0000-0000-000000000001', 'complete')$$,
  'learner cannot write progress for someone else');

begin;
select set_config('request.jwt.claims', json_build_object('sub', :'c')::text, true);
set local role authenticated;
update public.organizations set name = 'Hacked';
select pg_temp.check((select name = 'Acme Bank' from public.organizations), 'learner cannot rename the org');
commit;

-- ---- as bea again: admin rollups -------------------------------------------
begin;
select set_config('request.jwt.claims', json_build_object('sub', :'b')::text, true);
set local role authenticated;
select pg_temp.check((select count(*) = 2 from public.users), 'admin sees everyone in their org, no one else');
select pg_temp.check((select count(*) = 1 from public.user_progress), 'admin sees their org''s progress');
select pg_temp.check((select count(*) = 0 from public.tutor_conversations), 'admin cannot read learners'' tutor chats');
commit;

-- ---- anonymous --------------------------------------------------------------
select pg_temp.check_denied(null, $$select * from public.tracks$$, 'anonymous visitors cannot read content');

\echo 'All RLS checks passed.'
