# AutoSocial.tech — UI/UX Audit (Iteration 3)

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28
**Method:** live authenticated walkthrough on a local dev stack (SQLite, mock providers, backend-minted session token — no password entry, no production data touched) + source review. Seeded realistic fixtures (1 channel, 4 projects incl. short/long/rendering/failed, 1 publication) to exercise populated states.

## Screens reviewed (live)

### Dashboard (`/dashboard` → `pageFactoryDashboard`) — GOOD (real data)
Already an honest Video Factory dashboard. Cards: channels (active/testing/paused), projects-in-progress, rendered videos, **short/long split (added)**, queue (pending/processing + `N fail` inline), publications 7d/30d, YouTube views (honest `нет данных`), AI cost today/month, daily budget remaining. Plus: channel cards, an **alerts panel** where each item links to a real fix location (worker offline, project without scenes, channel without YouTube, stale analytics), a **real activity feed** ("no synthetic events"), and an **infrastructure strip** (Redis / Worker / render queue / FFmpeg / disk). Empty and error states exist.
- **Data source:** `GET /api/factory-dashboard` (`factory_dashboard_api.py`) — all real DB/queue/infra queries.
- **Fix applied:** short/long split (`videos_short`/`videos_long`, threshold 150s) + card.
- **No fake social metrics here.** ✅

### Video Projects (`/projects`) — GOOD (real data)
Channel selector, project list (title · status · date · Open/Download), "Создать проект", and a render-queue table with honest empty state. Real.

### Create Hub (`/create`) — P1 legacy emphasis
Leads with SMM: "Студия постов … для соцсетей", "Студия видео … **для Meta и YouTube**", 7-/30-day content plans; the real "Студия YouTube" is listed below. For a Video Factory the hub should lead with video/YouTube and de-emphasize posts/plans (keep the code).
- **Fix applied (partial):** video-studio subtitle reframed to the real YouTube production pipeline (ru). *Remaining: reorder hub to lead with Video/YouTube; move Posts/Plans under a "Social (legacy)" group; translate the reframed copy to en/de/es/fr/uk.*

### Admin (`/admin`) — P1 legacy SaaS console
Users + plans/credits + **"Панель выручки" (Stripe revenue/margin)** + "Сгенерировать статью". This is a SaaS admin, not Video-Factory ops. The **ops data the product actually needs already exists** (worker/queue/FFmpeg/disk via `infrastructure_status()` + `/api/readiness`, shown on the dashboard "Инфраструктура" strip and the "Система" page). Recommendation: make ops (Система) the primary admin surface; keep the SaaS user-admin behind a "Legacy/Billing" section. See `ADMIN-DASHBOARD.md`.

## Navigation — GOOD
Main sidebar is already Video-Factory-focused: Панель · Каналы · Ниши · Content Director · Видео-проекты · Публикации · Аналитика каналов · Подключения · Система · Выйти. Facebook/Instagram/Calendar/Billing do **not** dominate the main nav.

## Positioning — mostly fixed (Iter 2) + partial (Iter 3)
Entry points (17 shell titles/metas, landing title/description/OG, sidebar subtitle ×6 langs) now say **AI Video Factory / YouTube** instead of "AI SMM Manager / Facebook & Instagram / AI SaaS". Remaining in-app SMM copy (hundreds of strings: "соцсети", "Meta", posts, calendar, revenue, credits) to be reframed per-context, not by blind replace.

## Real vs mock
- **Real:** dashboard metrics, projects, render queue, publications, alerts, activity, infrastructure/health, admin user list, channels.
- **Legacy but real backend (keep, de-emphasize):** posts, content calendar/plans, Meta publishing, billing/credits, Stripe revenue panel, blog.
- **Mock/fabricated (remove):** landing testimonial ("перевёл наши соцсети на автопилот — вовлечённость выросла") and reach/engagement marketing lines. *(remaining)*
- **No `0`-instead-of-error found:** empty states are honest (`нет данных`, `Каналов пока нет`, `Событий пока нет`).

## Dev-environment note
The local static server (`python -m http.server`) has no SPA-fallback, so deep-linking `/create/video` 404s locally; production nginx rewrites to the SPA. Not a product bug. Navigate via the app router locally.

## Priorities remaining
- **P1:** Create Hub reorder (video-first, Posts/Plans → Social-legacy group); remove fabricated testimonial + social-metric marketing; make Система the primary admin.
- **P2:** finish in-app SMM copy reframing; visual consistency pass; loading/skeleton polish where missing.
