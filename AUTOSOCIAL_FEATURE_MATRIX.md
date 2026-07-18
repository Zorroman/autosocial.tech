# AutoSocial Feature Matrix (private YouTube-factory mode)

Statuses: working | partial | stub | broken | disabled | not implemented

| Feature | Frontend | Backend | Database | External dep | Tested | Status | Notes |
|---|---|---|---|---|---|---|---|
| Private admin auth (allowlist, fail closed) | yes | yes | yes | — | pytest + live | working | register всегда 403; старые сессии вне allowlist 403 |
| Admin bootstrap CLI | — | seed_admin.py | yes | — | manual | working | env-driven, без HTTP |
| Channels CRUD | /channels/ | channels_api.py | channels | — | pytest + browser | working | лимит 10, изоляция owner |
| Channel ideas (manual) | yes | yes | channel_ideas | — | pytest + browser | working | статусы new/saved/deferred/rejected/converted |
| Idea generation (AI) | yes | yes | yes | OpenAI | live (429) | partial | код рабочий; квота OpenAI исчерпана |
| Script generation | legacy create UI | content_pipeline | yes | OpenAI | no | partial | не привязано к каналу; квота |
| TTS | /projects/ (выбор голоса, тест, озвучка) | video/tts.py + video_projects_api | files + scene durations | Edge TTS (free) / OpenAI | live E2E (edge, ru-RU-DmitryNeural) | working | preflight без тихого fallback; OpenAI требует квоту |
| Stock media per scene | /projects/ (поиск, preview, выбор, auto-подбор) | video_projects_api + footage/providers/pexels | media_meta_json | Pexels (key set) | live E2E (3 клипа) | working | SSRF-safe select; portrait приоритет; source/license сохраняются |
| Subtitles (ASS/SRT, 9:16) | — | video/subtitles.py + render | files | — | render test | working | вожжены в тестовый MP4 |
| FFmpeg render 1080x1920 Shorts | — | video/render | files | ffmpeg 7.1.1 | pytest + ffprobe | working | test_esoteric_short.mp4 |
| Render queue | — | saas_queue + RQ | generation jobs | Redis (optional) | pytest (sync) | partial | thread-fallback теряет задачи при рестарте |
| Render Queue (backend) | — | video_projects_api.py | render_jobs | Redis (opt) | pytest + live RQ | working | статусы/progress/attempts/retry/cancel; thread-fallback теряет задачи при рестарте |
| Render Queue UI | /projects/ | yes | yes | — | browser | working | прогресс, попытки, ошибки, retry, cancel, download |
| Video projects w/ scenes per channel | /projects/ | video_projects_api.py | video_projects, video_scenes | — | pytest + browser E2E | working | сценарий→сцены→медиа→рендер→MP4→download |
| Scene fixture media (local) | yes | yes | files | ffmpeg | E2E | working | честная фикстура, visual_type='fixture' |
| Media library UI | no | /api/media serve | files | — | live | partial | serve hardened (dotfiles, root allowlist) |
| YouTube OAuth connect | /connections/ + /channels/ (link/verify) | saas_api + publications_api | social_accounts + channels | Google OAuth | UI (без реального OAuth-клика) | partial | scope upload добавлен; refresh_token сохраняется; нужно переподключение |
| YouTube publications (manual-first) | /publications/ + редактор в проекте | publications_api.py | publications | — | live UI E2E | working | prepare→edit→download→manual-complete→published |
| YouTube auto-upload | кнопка в публикации | publications_api.py (resumable upload, refresh, quota) | publications | YouTube Data API | mocked tests only | partial | реальный upload не выполнялся (по правилу этапа) |
| Channel analytics (manual + Data API sync) | /factory-analytics/ | analytics_api.py | video_analytics_snapshots | YouTube Data API (readonly, mocked) | pytest + browser | working | manual live; API sync mocked (реальный OAuth не запускался); watch time/revenue только manual |
| AI cost tracking + budgets | /factory-analytics/ | ai_pricing.py + record_cost hooks | ai_cost_records | — | pytest + browser | working | цены централизованы (env-override); unknown=NULL; free ops=0; бюджеты блокируют платные операции |
| Public registration | removed | 403 | — | — | pytest | disabled | |
| Pricing / trial / billing UI | removed | legacy routes остались | yes | Stripe | grep | disabled | UI убран; endpoints за require_auth |
| Stripe subscriptions | hidden | stripe_service.py | yes | Stripe | no | disabled | legacy code |
| Meta (FB/IG) posting | legacy UI | facebook_api.py | yes | Meta API | no | partial | вне scope фабрики |
| Frontend integrity gate | — | scripts/check_frontend_integrity.sh | — | node, python | live | working | syntax + UTF-8 + '????' + sha256 |
| Factory Dashboard (aggregated) | /dashboard/ | factory_dashboard_api.py | — | — | pytest + browser | working | один запрос; NULL вместо fake-нулей; alerts со ссылками |
| Readiness + worker heartbeat | /factory-settings/ | /api/readiness, RQ Worker.all | — | Redis (opt) | pytest + live | working | critical/optional разделены; секреты не возвращаются |
| Runtime cleanup | CLI | scripts/cleanup_runtime.py | — | — | pytest (dry-run) | working | dry-run default; execute требует подтверждения |
| Pre-deploy gate | CLI | scripts/predeploy_check.sh | — | — | live | working | git clean + UTF-8 + JS + тесты; .env не копируется |
