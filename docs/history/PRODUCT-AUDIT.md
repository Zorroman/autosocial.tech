# AutoSocial.tech — Product Audit (Iteration 1)

**Branch:** `feature/admin-dashboard-polish`
**Date:** 2026-07-28
**Auditor scope:** repositioning + UI/UX audit. Goal: make the interface honest, consistent, and demo-ready for an employer/client, positioned as an **AI Video Factory** (automated short/long video production → YouTube), NOT a social-media SaaS.

> **Method & honest limitations.** Public pages (landing, login) were audited live in a browser. Authenticated areas (dashboard, create, history, admin) were audited from source (`frontend/app.js`, HTML shells, backend routes) — a live authenticated walkthrough was **not** performed because signing in requires entering credentials, which the assistant does not do. Live authenticated verification is a follow-up item (needs an operator-provided session).

---

## 1. Structure (verified)

- **Frontend:** vanilla-JS SPA. One file, `frontend/app.js` (**19,443 lines**), drives every page; each route has a thin static HTML shell under `frontend/<page>/`. Styles in `frontend/styles.css`.
- **Backend:** Flask (`saas_api.py` + domain modules), served at `api.autosocial.tech`.
- **Worker:** `worker.py` (RQ) — factory scheduler + long-form scheduler + render/publish jobs.
- **DB:** PostgreSQL (prod). **Deployment:** Docker Compose on Hetzner (backend, worker, redis, postgres, nginx).
- **Live URLs:** site `https://autosocial.tech`, API `https://api.autosocial.tech`.

### Routes registered in the SPA (`app.js` router)
`/login`, `/dashboard` (→ factory dashboard), `/create`, `/create/post`, `/create/video`, `/create/plan`, `/calendar`, `/channels`, `/projects`, `/publications`, `/content-director`, `/niches`, `/connections`, `/youtube`, `/history`, `/factory-analytics`, `/factory-settings`, `/analytics`, `/billing`, `/settings`, `/admin`, `/blog`, `/contact`, `/support`, `/trial-activated`.

---

## 2. The core problem: hybrid positioning

The product contains **two overlapping worlds**:

| Legacy SMM/social world | Real "Video Factory" world (in active use) |
|---|---|
| Social **posts** → Meta (Facebook/Instagram) | Short/long **videos** → YouTube |
| Calendar, reach/engagement/impressions metrics | Pipeline stages (script→voice→media→render→publish) |
| "AI SMM Manager", billing/credits (SaaS) | Channels, Content Director, factory dashboard |

The **entry points present the SMM/SaaS world**, which is the wrong story for this product's real capability and for a portfolio demo.

### Positioning terms found (frontend, user-visible; backups excluded)
- **"Facebook": 218** · **"Instagram": 182** · **"SaaS": 49** · **"соцсет*": 24** · **"social media": 4** · **"AI Video Factory": 0**
- Landing `<title>`: *"AutoSocial.tech — автоматизация SMM, публикации и контент"*
- Dashboard/login `<meta description>`: *"…an AI SMM Manager that generates strategy, creates content and auto-publishes to **Facebook and Instagram**."*
- Landing hero (live): logo subtitle **"AI SMM Manager"**; *"Для… in-house SMM"*; *"Генерируйте посты и видео соцсетей"*.
- Dashboard i18n keys for **sort by reach / engagement / impressions** (social metrics, not video-production metrics).
- Testimonial (fabricated): *"…перевёл наши соцсети на автопилот… вовлечённость выросла" — Маркетолог, SMB* (fake social proof — should be removed or made honest).

---

## 3. Findings by state

### Working (real backend, verified in code / this session's operation)
- **YouTube video factory pipeline** end-to-end: Director → script → scenes → media → render (FFmpeg) → QC → metadata → publish. Confirmed publishing live this session (Shorts + long-form).
- **Channels**, **Connections** (Meta + YouTube OAuth), **Content Director**, **History/Calendar**, **Publications**, **Factory dashboard/analytics/settings**, **Niches** — backed by real routes.
- **Auth** (email code, Google/Facebook OAuth), sessions.

### Partial / honestly-stubbed
- **Billing** — labeled *"Скоро доступно" / "Coming soon"* (`billing_coming_soon`). It is a stub; acceptable **only** because it's labeled unavailable. For a video-factory demo, billing/credits (a SaaS concept) is arguably out of scope and could be hidden.
- **Analytics / dashboard social metrics** — reach/engagement/impressions sort options exist; these map to the SMM/post world, not video production. Need to confirm whether they render real data or empty.

### Positioning-wrong (P1) — real functionality, wrong framing
- Titles, meta descriptions, OG tags, landing hero, logo subtitle "AI SMM Manager".
- Fabricated SMM testimonial and "reach/engagement" marketing lines.

### To verify live (pending — needs authenticated session)
- Dashboard: does it show real counts (created / published / in-queue / errors) or social vanity metrics?
- Create flow: are all form fields consumed by the backend (no ghost fields)?
- Pipeline: do statuses update without reload; is retry/cancel wired?
- History: filters, preview, download, YouTube link, re-run, delete safety.
- Admin: which sections have real data vs empty; dangerous actions have confirmations?
- Console errors, broken API calls, responsive at 375/768/1024/1440/1920.

---

## 4. Prioritized problem list

**P0 (blocking / unsafe)** — none proven yet; **must verify live**: login works, dashboard loads, create works, pipeline updates, no exposed secrets, dangerous admin actions gated. (Backend pipeline is confirmed healthy from this session.)

**P1 (wrong data / positioning / broken UX)**
1. Entry-point positioning is SMM/SaaS, not Video Factory (title, meta, OG, hero, logo subtitle). *(fix started, Iteration 2)*
2. Fabricated SMM testimonial + reach/engagement marketing claims.
3. Dashboard/analytics may surface social vanity metrics instead of production metrics (created/published/queued/failed). *(verify)*
4. "SaaS"/"соцсети"/Meta-first language throughout in-app copy where the real flow is YouTube video production.

**P2 (polish)**
- Spacing/typography/card consistency, loading/empty/error states, responsive tables/modals, tooltips — per `UI-UX-AUDIT.md` (to be produced).

---

## 5. Plan (iterations)

- **Iter 2 (positioning P1):** reframe entry points to AI Video Factory — HTML shell titles/meta/OG, landing hero + logo subtitle, remove/replace fabricated testimonial & social-metric marketing lines. No feature changes; text-only, reversible.
- **Iter 3:** dashboard = real production metrics (created / published / in queue / errors / next action); audit create flow field-parity; pipeline status truthfulness.
- **Iter 4:** admin sections vs real data; queue/logs/health; confirmations on dangerous actions.
- **Iter 5:** responsive + loading/empty/error states + visual consistency.
- **Iter 6:** Playwright critical flows; end-to-end short + long test in a safe/mock mode; finalize `UI-UX-AUDIT.md`, `ADMIN-DASHBOARD.md`, `DEMO-READINESS.md`.

**Rules honored:** separate branch, no `main` commits, no secret exposure, no deletion of user data/projects, no breaking the working pipeline, audit-before-fix.
