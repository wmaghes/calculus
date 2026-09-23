# Fluency: AI literacy platform

Self-paced, interactive AI literacy courses for working professionals, sold to
companies as seats. Built with Next.js 16 (App Router), TypeScript, Tailwind v4
and Supabase (Postgres, Auth, row-level security), hosted on Vercel.

"Fluency" is a working name, set in `src/lib/brand.ts`.

## Build status

| Stage | Scope | Status |
| --- | --- | --- |
| 1 · Foundation | Schema + RLS, Supabase Auth (email/password + Google), design system | ✅ built |
| 2 · Core pages | Dashboard, module page with tutor slide-out, quiz page | next |
| 3 · API wiring | Claude tutor + grading, ElevenLabs narration, Arcade embeds | |
| 4 · Pilot content | Module 1, "What an LLM Actually Is (and Isn't)" | |
| 5 · Admin | org_admin dashboard with CSV export | |

## Run it locally

```bash
cd platform
npm install
cp .env.example .env.local   # fill in your Supabase URL + publishable key
npm run dev                  # http://localhost:3000
```

`/design` shows every design-system component and works without Supabase.
The sign-in pages show a setup notice until `.env.local` is filled in.

## Supabase setup

1. Create a project, then apply the migration in
   `supabase/migrations/`. Either run `supabase link && supabase db push`, or
   paste the file into the SQL editor.
2. **Auth → URL configuration:** set Site URL to your app's URL and add
   `http://localhost:3000/**` and your Vercel URL (`https://*.vercel.app/**`)
   to the redirect allow-list.
3. **Auth → Providers → Google:** enable it with a Google Cloud OAuth client.
   The client's authorised redirect URI is
   `https://<project-ref>.supabase.co/auth/v1/callback`.
4. Optional: to make confirmation links work when opened in a different
   browser, change the "Confirm signup" email template link to
   `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=email`.
5. Once linked, `npm run db:types` regenerates `src/lib/database.types.ts`
   from the live schema.

## Data model and tenancy

Tables follow the build spec: `organizations`, `users`, `tracks`, `modules`,
`lessons`, `quiz_questions`, `user_progress`, `certificates`,
`tutor_conversations`. On top of the spec:

- `org_invitations`: company rollouts invite an email into an org.
- `tracks.organization_id`: null means a global catalog track; set means the
  track is private to that org.
- `organization_id` on `user_progress`, `certificates` and
  `tutor_conversations`: set by a trigger, never by the client. RLS and admin
  rollups filter on it.
- `lessons.title` and `quiz_questions.order_index`: the sidebar and the quiz
  need them.

**How signup assigns an org:** a trigger on `auth.users` creates the
`public.users` row. A pending invitation is honoured only when the address is
proven, either because an admin invited them (`auth.admin.inviteUserByEmail`)
or because the provider verified the email (Google). Every other signup gets a
personal org of one on the `individual` plan.

**Who can do what (RLS plus column grants):**

| | Learner | org_admin | Server (service role) |
| --- | --- | --- | --- |
| Own profile | read, edit name | same | all |
| Org's users / progress / certificates | own rows only | whole org | all |
| Tutor conversations | own only | own only (private) | all |
| Content | global + own org's tracks | same | write |
| `quiz_questions.correct_answer` | ✗ | ✗ | read (grading) |
| `user_progress.score`, roles, plan, seats | ✗ | ✗ | write |
| Invitations | ✗ | manage own org's | all |

**Test it:** `npm run test:db` spins up a throwaway local Postgres, applies the
migrations over a stub of Supabase's `auth` schema, and runs 26 RLS checks
from `supabase/tests/local/rls_test.sql`. It needs Postgres server binaries
installed.

**Rule for future migrations:** the foundation migration revokes the default
Supabase grants on `public`. Every new table needs explicit `grant`s and RLS
policies, or learners can't read it.

## Design system

Tokens live in `src/app/globals.css`. Tailwind's default palette is disabled
(`--color-*: initial`), so only the brand tokens exist.

- **Color:** near-black ink scale plus one amber accent (`#FFB224`) for CTAs,
  progress and active states. Green and red are only for answer feedback.
- **Type:** Inter Tight for display, Inter for body, JetBrains Mono for
  eyebrows and tokens. Display is 64px and body 15–17px, so the hierarchy
  stays strong.
- **Motion:** rings and bars fill on load and ease between values. The
  completion check pops and draws in. Cards lift 2px on hover. All of it
  respects `prefers-reduced-motion`.

| Component | File |
| --- | --- |
| `Button`, `ButtonLink` | `src/components/ui/button.tsx` |
| `Card`, `CardLink` | `src/components/ui/card.tsx` |
| `ProgressRing`, `ProgressBar` | `src/components/ui/progress.tsx` |
| `CompleteCheck`, `StatusDot` | `src/components/ui/complete-check.tsx` |
| `Field` | `src/components/ui/field.tsx` |
| `Badge`, `Eyebrow`, `Container`, `Prose` | `src/components/ui/typography.tsx` |
| `AppNav`, `StreakChip` | `src/components/nav/app-nav.tsx` |
| `TrackCard`, `ModuleTile` | `src/components/course/` |
| `Logo`, `LogoMark` | `src/components/brand/logo.tsx` |

## Scripts

- `npm run dev` / `npm run build`
- `npm run lint` / `npm run typecheck`
- `npm run test:db`: RLS tests against a local Postgres
- `npm run db:types`: regenerate DB types (needs a linked Supabase project)
