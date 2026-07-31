# Create-Video Field Matrix

**Branch:** `feature/admin-dashboard-polish` · **Date:** 2026-07-28
Source: `content_director_api.py`, `content_director.py` (`handoff_to_writer`), `video_projects_api.py` (`generate-script`, `split-scenes`, `render`), `video_script_generator.py`, `saas_models.py`.

> **Scope honesty.** The video flow is **Director-driven**, not a flat form: you pick a channel/idea, the Content Director produces a strategy, and approving it creates the `VideoProject`, which then runs script → scenes → media → render → publish. The table below maps the **effective inputs** that reach the pipeline (verified in code). The `/create/video` studio's per-widget UI parity (every control ↔ payload key) is **partially verified** — deeper per-widget audit is a remaining item.

| Input | Short | Long | Where set | Backend field | Stored | Worker uses | Effect on video | Verified |
|---|---|---|---|---|---|---|---|---|
| Topic / idea | ✅ | ✅ | Director strategy | `VideoProject.title` (via `handoff_to_writer`) | ✅ | script generator | drives the whole script | ✅ code |
| Channel | ✅ | ✅ | studio selector | `VideoProject.channel_id` | ✅ | all stages (niche/voice/lang inherited) | which channel/persona/YouTube target | ✅ code |
| Duration (short/long) | ✅ 45s | ✅ 720s | channel default `default_video_duration_seconds` → `duration_target_seconds` | `VideoProject.duration_target_seconds` | ✅ | `generate()` picks long path at ≥150s; render length | short vs long pipeline | ✅ code+live |
| Language | ✅ | ✅ | channel `language` | passed to `generate-script` | ✅ (channel) | TTS + script | narration language | ✅ code |
| Niche | ✅ | ✅ | channel `niche_id` | `Channel.niche_id` | ✅ | Director + media queries | topic framing + footage | ✅ code |
| Voice | ✅ | ✅ | channel `default_voice` (+ persona) | `Channel.default_voice`, `generation_settings_json.persona` | ✅ | `synthesize_voiceover` | narrator voice + authorial voice | ✅ code+live |
| Visual source | ✅ | ✅ | pipeline (Pexels/Pixabay) | scene `selected_media_path` / long-form photo manifest | ✅ | media matcher / footage | on-screen footage | ✅ code |
| Music | ✅ | ✅ | server music library | env `VIDEO_BG_MUSIC_*` / `MUSIC_LIBRARY_DIR` | config | final mix | background bed | ✅ code |
| Subtitles | ✅ | ✅ | pipeline | `.ass` built from timings (long-form: Whisper-aligned) | file | render burn-in | burned captions | ✅ code |
| Publishing mode | ✅ | ✅ | channel `publishing_mode` + project override | `Channel.publishing_mode` | ✅ | publish gate | manual vs automatic | ✅ code |
| YouTube channel | ✅ | ✅ | channel connection | `Channel.youtube_social_account_id` | ✅ | upload | target account | ✅ code |
| Privacy | ✅ | ✅ | AI Publisher / channel `default_visibility` | `youtube_meta_json.privacy` / `Publication.privacy_status` | ✅ | upload | public/unlisted/private | ✅ code |
| Schedule | ✅ | ✅ | publication `publish_mode=scheduled` + `scheduled_at` | `Publication.scheduled_at` | ✅ | upload | scheduled publish | ✅ code |

## Findings
- **No obvious ghost fields at the pipeline level** — the inputs above all reach a real backend field and affect the output. Because the flow is Director-driven, most "fields" are inherited from the **channel**, not typed per-video.
- **Remaining:** audit the `/create/video` studio widget-by-widget (e.g. any decorative toggles in the Director UI that don't map to a payload key). Not completed this iteration.
- **Post-create UX** (task requirement): after create, the app routes to the project/pipeline view; a toast + job-id confirmation + "continues in background" messaging should be verified/added — **remaining**.
- **Double-submit protection:** the render path has duplicate-render protection (`test_duplicate_render_protection` passes) and the publish path is idempotent (`youtube_video_id` guard). The create-form submit-lock UX itself is **not yet verified**.
