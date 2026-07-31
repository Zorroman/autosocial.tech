# Pipeline & Job Status Matrix

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28 · Source of truth: `factory_pipeline.py`, `longform_pipeline.py`, `saas_models.py` (VideoProject / RenderJob / Publication), `factory_dashboard_api.py`.

The Video Factory tracks state on **three real entities**, not one universal enum. The UI should map each honestly.

## 1. VideoProject.pipeline_stage → pipeline_state (the conveyor)
Stages (in order): **script → scenes → media → render → publish** (factory) / for long-form the same stages back the `longform_pipeline` steps (script→visual_groups→photos→voiceover→subtitles→graphics→render→final_mix→publish).

| pipeline_state | Meaning | UI label | Badge | Terminal | Retry | Cancel |
|---|---|---|---|---|---|---|
| `running` | stage in progress | «Выполняется» | blue/spinner | no | no | (only via safe stop) |
| `needs_review` | stopped at human checkpoint / recoverable failure | «Требует внимания» | amber | no | yes (re-run station) | n/a |
| `error` | station failed | «Ошибка» | red | no | yes | n/a |
| `done` | stage complete | «Готово» | green | yes (for stage) | no | no |
| (null stage) | not entered the factory line | «Черновик» | grey | — | — | — |

Self-healing: a project stuck in `running` beyond `FACTORY_RUNNING_STALE_MIN` (30 min) is auto-reset to `needs_review` by the scheduler (commit `2fa6d86`) — no dead job blocks generation.

## 2. VideoProject.status (coarse lifecycle)
`draft → ready → rendering → rendered`. Dashboard counts: `projects_in_progress = {draft, ready, rendering}`, `videos_rendered = {rendered}`.

## 3. RenderJob.status (the render worker)
| status | UI label | Badge | Terminal | Retry |
|---|---|---|---|---|
| `pending` | «В очереди» | grey | no | no |
| `processing` | «Рендер» | blue | no | no |
| `completed` | «Готово» | green | yes | no |
| `failed` | «Ошибка рендера» | red | yes | yes (safe — idempotent) |

Dashboard: `jobs_pending / jobs_processing / jobs_failed` shown on the "Очередь" card (`N fail` in red).

## 4. Publication.status (YouTube publishing)
| status | UI label | Badge | Terminal | Notes |
|---|---|---|---|---|
| `draft` | «Черновик» | grey | no | metadata prepared |
| `ready` | «Готово к публикации» | grey | no | |
| `uploading` | «Загрузка на YouTube» | blue | no | idempotent — no double-upload (`youtube_video_id` guard) |
| `published` | «Опубликовано» | green | yes | links to `youtube_url` |
| `failed` | «Ошибка публикации» | red | yes | `last_error`; project → needs_review, never auto-retries to avoid duplicate upload |

## UI requirements (mapping rules)
- **Unknown status → safe fallback** «Неизвестно» (grey), never a raw enum.
- Completed stages persist after reload (state is server-side on the project/job/publication).
- `publishing` (uploading) and `published` are **distinct** — do not merge.
- Retry is offered **only** for `failed` render jobs and `needs_review`/`error` project stages, with confirmation; the publish path is idempotent by design.
- Raw JSON / stack traces / server paths → collapsible "technical details" only.

## Note on short vs long
Short (factory `render_video`) and long (`longform_pipeline`) differ in the render internals but share the **same stage names and the same publish entity/status**, so one status mapping covers both. The known difference: long-form runs via the RQ queue (serialized with shorts); shorts via the same queue. No separate status vocabulary needed.
