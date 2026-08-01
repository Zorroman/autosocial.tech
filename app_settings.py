import os
from pathlib import Path


class Settings:
    BASE_DIR = Path(os.getenv("BASE_DIR", Path(__file__).resolve().parent)).resolve()
    CACHE_DIR = (BASE_DIR / "cache").resolve()
    OUTPUT_DIR = (BASE_DIR / "output").resolve()
    FOOTAGE_CACHE_DIR = (CACHE_DIR / "footage").resolve()
    OUTPUT_VIDEOS_DIR = (OUTPUT_DIR / "videos").resolve()
    OUTPUT_AUDIO_DIR = (OUTPUT_DIR / "audio").resolve()
    OUTPUT_SUBTITLES_DIR = (OUTPUT_DIR / "subtitles").resolve()
    OUTPUT_MANIFESTS_DIR = (OUTPUT_DIR / "manifests").resolve()
    FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"
    FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe").strip() or "ffprobe"
    VIDEO_RENDER_CONCURRENCY = max(1, int(os.getenv("VIDEO_RENDER_CONCURRENCY", "2")))
    VIDEO_MAX_ACTIVE_RENDERS = max(1, int(os.getenv("VIDEO_MAX_ACTIVE_RENDERS", str(VIDEO_RENDER_CONCURRENCY))))
    VIDEO_MAX_QUEUED_PER_USER = max(1, int(os.getenv("VIDEO_MAX_QUEUED_PER_USER", "30")))
    VIDEO_MAX_QUEUED_GLOBAL = max(1, int(os.getenv("VIDEO_MAX_QUEUED_GLOBAL", "200")))
    VIDEO_AUTO_RETRY_TRANSIENT = max(0, int(os.getenv("VIDEO_AUTO_RETRY_TRANSIENT", "1")))
    VIDEO_QUEUE_AVG_RENDER_SECONDS = max(30, int(os.getenv("VIDEO_QUEUE_AVG_RENDER_SECONDS", "180")))
    VIDEO_CROSS_VIDEO_DEDUP_DAYS = max(0, int(os.getenv("VIDEO_CROSS_VIDEO_DEDUP_DAYS", "30")))
    VIDEO_CROSS_VIDEO_DEDUP_MAX_MANIFESTS = max(20, int(os.getenv("VIDEO_CROSS_VIDEO_DEDUP_MAX_MANIFESTS", "200")))
    VIDEO_AVOID_DUPLICATE_FOOTAGE = os.getenv("VIDEO_AVOID_DUPLICATE_FOOTAGE", "true").lower() in {"1", "true", "yes"}
    VIDEO_SUBTITLE_MODE = (os.getenv("VIDEO_SUBTITLE_MODE", "auto").strip().lower() or "auto")
    VIDEO_PLATFORM_TARGET = (os.getenv("VIDEO_PLATFORM_TARGET", "generic").strip().lower() or "generic")
    VIDEO_SUBTITLE_STYLE = (os.getenv("VIDEO_SUBTITLE_STYLE", "social_default").strip().lower() or "social_default")
    VIDEO_MIN_UNIQUE_CLIPS_SHORT = max(4, int(os.getenv("VIDEO_MIN_UNIQUE_CLIPS_SHORT", "8")))
    VIDEO_FALLBACK_RELATED_KEYWORDS = os.getenv("VIDEO_FALLBACK_RELATED_KEYWORDS", "true").lower() in {"1", "true", "yes"}
    VIDEO_DIVERSITY_MODE = (os.getenv("VIDEO_DIVERSITY_MODE", "balanced").strip().lower() or "balanced")
    VIDEO_ALLOW_EMERGENCY_REUSE = os.getenv("VIDEO_ALLOW_EMERGENCY_REUSE", "true").lower() in {"1", "true", "yes"}
    OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "eddy").strip() or "eddy"
    # Dynamic footage segmentation and repeat protection.
    FOOTAGE_SEGMENT_SECONDS = float(os.getenv("FOOTAGE_SEGMENT_SECONDS", "3.0"))
    FOOTAGE_SEGMENT_MIN_SECONDS = float(os.getenv("FOOTAGE_SEGMENT_MIN_SECONDS", "2.5"))
    FOOTAGE_SEGMENT_MAX_SECONDS = float(os.getenv("FOOTAGE_SEGMENT_MAX_SECONDS", "3.5"))
    FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS = int(os.getenv("FOOTAGE_SAME_CHANNEL_COOLDOWN_DAYS", "30"))
    FOOTAGE_GLOBAL_COOLDOWN_DAYS = int(os.getenv("FOOTAGE_GLOBAL_COOLDOWN_DAYS", "7"))
    # Hard long-term rule (Media Diversity Engine): a clip stays excluded until
    # BOTH thresholds clear -- whichever is later, not whichever is first. This
    # is stricter than, and layered on top of, the softer same-channel/global
    # cooldowns above (which stay as scoring penalties, not hard exclusions).
    FOOTAGE_LONG_TERM_COOLDOWN_DAYS = int(os.getenv("FOOTAGE_LONG_TERM_COOLDOWN_DAYS", "90"))
    FOOTAGE_LONG_TERM_COOLDOWN_USES = int(os.getenv("FOOTAGE_LONG_TERM_COOLDOWN_USES", "500"))
    # How many of the channel's most recent categories to penalize a repeat of.
    FOOTAGE_CATEGORY_MEMORY = int(os.getenv("FOOTAGE_CATEGORY_MEMORY", "5"))
    FOOTAGE_ALLOW_REUSE_FALLBACK = os.getenv("FOOTAGE_ALLOW_REUSE_FALLBACK", "true").lower() in {"1", "true", "yes"}
    FOOTAGE_RESERVATION_TTL_SECONDS = int(os.getenv("FOOTAGE_RESERVATION_TTL_SECONDS", "1800"))
    # Search budget before a reuse is ever allowed (mass-generation safety).
    PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT = max(1, int(os.getenv("PEXELS_MAX_SEARCH_QUERIES_PER_SEGMENT", "4")))
    PEXELS_MAX_PAGES_PER_QUERY = max(1, int(os.getenv("PEXELS_MAX_PAGES_PER_QUERY", "2")))
    PEXELS_CANDIDATES_PER_SEGMENT = max(1, int(os.getenv("PEXELS_CANDIDATES_PER_SEGMENT", "12")))
    FOOTAGE_REUSE_ONLY_AFTER_EXHAUSTED_SEARCH = os.getenv("FOOTAGE_REUSE_ONLY_AFTER_EXHAUSTED_SEARCH", "true").lower() in {"1", "true", "yes"}
    TOPIC_COOLDOWN_DAYS = int(os.getenv("TOPIC_COOLDOWN_DAYS", "60"))
    TOPIC_DUPLICATE_THRESHOLD = float(os.getenv("TOPIC_DUPLICATE_THRESHOLD", "0.6"))
    TOPIC_MAX_GENERATION_ATTEMPTS = max(1, int(os.getenv("TOPIC_MAX_GENERATION_ATTEMPTS", "3")))
    # AI Content Director (decides WHAT to film next, never writes the script)
    DIRECTOR_ENABLED = os.getenv("DIRECTOR_ENABLED", "true").lower() in {"1", "true", "yes"}
    DIRECTOR_USE_AI = os.getenv("DIRECTOR_USE_AI", "true").lower() in {"1", "true", "yes"}
    DIRECTOR_CANDIDATES_PER_RUN = max(1, int(os.getenv("DIRECTOR_CANDIDATES_PER_RUN", "6")))
    DIRECTOR_DUPLICATE_THRESHOLD = float(os.getenv("DIRECTOR_DUPLICATE_THRESHOLD", "0.55"))
    DIRECTOR_PILLAR_RECENCY_PENALTY = float(os.getenv("DIRECTOR_PILLAR_RECENCY_PENALTY", "0.5"))
    DIRECTOR_ANALYTICS_WEIGHT = float(os.getenv("DIRECTOR_ANALYTICS_WEIGHT", "0.3"))
    # Visual AI validation of footage candidates
    VISUAL_VALIDATION_ENABLED = os.getenv("VISUAL_VALIDATION_ENABLED", "false").lower() in {"1", "true", "yes"}
    VISUAL_VALIDATION_FAIL_OPEN = os.getenv("VISUAL_VALIDATION_FAIL_OPEN", "true").lower() in {"1", "true", "yes"}
    VISUAL_RELEVANCE_MIN_SCORE = float(os.getenv("VISUAL_RELEVANCE_MIN_SCORE", "0.55"))
    VISUAL_SUBJECT_MIN_SCORE = float(os.getenv("VISUAL_SUBJECT_MIN_SCORE", "0.4"))
    VISUAL_ACTION_MIN_SCORE = float(os.getenv("VISUAL_ACTION_MIN_SCORE", "0.3"))
    VISUAL_MAX_CANDIDATES_PER_SEGMENT = max(1, int(os.getenv("VISUAL_MAX_CANDIDATES_PER_SEGMENT", "5")))
    VISUAL_FRAME_COUNT = max(1, int(os.getenv("VISUAL_FRAME_COUNT", "5")))
    VISUAL_AI_DAILY_BUDGET_USD = float(os.getenv("VISUAL_AI_DAILY_BUDGET_USD", "2.0"))
    VISUAL_AI_MAX_CHECKS_PER_VIDEO = max(1, int(os.getenv("VISUAL_AI_MAX_CHECKS_PER_VIDEO", "30")))
    VISUAL_AI_MAX_CHECKS_PER_SEGMENT = max(1, int(os.getenv("VISUAL_AI_MAX_CHECKS_PER_SEGMENT", "3")))
    VISUAL_AI_CACHE_TTL_DAYS = max(1, int(os.getenv("VISUAL_AI_CACHE_TTL_DAYS", "90")))
    VISUAL_AI_MODEL = os.getenv("VISUAL_AI_MODEL", "gpt-4o-mini").strip()
    VISUAL_AI_PROVIDER = os.getenv("VISUAL_AI_PROVIDER", "mock").strip().lower()
    VIDEO_CLIP_FADE_SECONDS = float(os.getenv("VIDEO_CLIP_FADE_SECONDS", "0.2"))
    SUBTITLE_MAX_LINE_CHARS = int(os.getenv("SUBTITLE_MAX_LINE_CHARS", "36"))
    SUBTITLE_MARGIN_BOTTOM_PX = int(os.getenv("SUBTITLE_MARGIN_BOTTOM_PX", "380"))
    SUBTITLE_FONT_NAME = os.getenv("SUBTITLE_FONT_NAME", "Arial").strip() or "Arial"
    SUBTITLE_HIGHLIGHT_KEYWORD = os.getenv("SUBTITLE_HIGHLIGHT_KEYWORD", "false").lower() in {"1", "true", "yes"}
    VIDEO_BG_MUSIC_ENABLED = os.getenv("VIDEO_BG_MUSIC_ENABLED", "false").lower() in {"1", "true", "yes"}
    VIDEO_BG_MUSIC_PATH = os.getenv("VIDEO_BG_MUSIC_PATH", "").strip()
    MEDIA_AUTOFIX_ENABLED = os.getenv("MEDIA_AUTOFIX_ENABLED", "false").lower() in {"1", "true", "yes"}
    MEDIA_AUTOFIX_INTERVAL_SECONDS = max(60, int(os.getenv("MEDIA_AUTOFIX_INTERVAL_SECONDS", "600")))
    MEDIA_AUTOFIX_BATCH_SIZE = max(1, int(os.getenv("MEDIA_AUTOFIX_BATCH_SIZE", "4")))

    USE_MOCK_PROVIDERS = os.getenv("USE_MOCK_PROVIDERS", "false").lower() in {"1", "true", "yes"}
    MOCK_META = os.getenv("MOCK_META", "false").lower() in {"1", "true", "yes"}
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SYNC_JOBS = os.getenv("SYNC_JOBS", "false").lower() in {"1", "true", "yes"}
    ENV = os.getenv("ENV", "development")
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000").rstrip("/")
    META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "").strip()
    FB_LOGIN_REDIRECT_URI = os.getenv("FB_LOGIN_REDIRECT_URI", "").strip()
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "").strip()
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", FRONTEND_BASE_URL)
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
    SHOW_SOCIAL_LOGIN = os.getenv("SHOW_SOCIAL_LOGIN", "false").lower() in {"1", "true", "yes"}
    ALLOW_ADMIN_DIRECT_LOGIN = os.getenv("ALLOW_ADMIN_DIRECT_LOGIN", "false").lower() in {"1", "true", "yes"}
    # Private single-admin mode: registration disabled, every authenticated request
    # requires the user's email to be in ADMIN_ALLOWLIST_EMAILS. Fail closed:
    # an empty allowlist in private mode denies all access instead of opening up.
    PRIVATE_ADMIN_MODE = os.getenv("PRIVATE_ADMIN_MODE", "true").lower() in {"1", "true", "yes"}
    ADMIN_ALLOWLIST_EMAILS: set = {
        e.strip().lower()
        for e in os.getenv("ADMIN_ALLOWLIST_EMAILS", "").split(",")
        if e.strip()
    }

    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_PRICE_INPUT_PER_1M = float(os.getenv("OPENAI_PRICE_INPUT_PER_1M", "0.15"))
    OPENAI_PRICE_OUTPUT_PER_1M = float(os.getenv("OPENAI_PRICE_OUTPUT_PER_1M", "0.60"))
    CREDIT_MULTIPLIER = float(os.getenv("CREDIT_MULTIPLIER", "1"))
    AVG_TOKENS_PER_POST = int(os.getenv("AVG_TOKENS_PER_POST", "1200"))
    SOFT_LIMIT_RATIO = float(os.getenv("SOFT_LIMIT_RATIO", "0.9"))
    OVERDRAFT_LIMIT = int(os.getenv("OVERDRAFT_LIMIT", "-10000"))

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_STARTER = os.getenv("STRIPE_PRICE_STARTER", "")
    STRIPE_PRICE_GROWTH = os.getenv("STRIPE_PRICE_GROWTH", "")
    STRIPE_PRICE_PRO_V2 = os.getenv("STRIPE_PRICE_PRO_V2", "")
    STRIPE_PRICE_AGENCY_V2 = os.getenv("STRIPE_PRICE_AGENCY_V2", "")
    STRIPE_PRICE_LIGHT = os.getenv("STRIPE_PRICE_LIGHT", "")
    STRIPE_PRICE_PRO = os.getenv("STRIPE_PRICE_PRO", "")
    STRIPE_PRICE_AGENCY = os.getenv("STRIPE_PRICE_AGENCY", "")
    STRIPE_PACK_S_PRICE = os.getenv("STRIPE_PACK_S_PRICE", "")
    STRIPE_PACK_M_PRICE = os.getenv("STRIPE_PACK_M_PRICE", "")
    STRIPE_PACK_L_PRICE = os.getenv("STRIPE_PACK_L_PRICE", "")
    STRIPE_PORTAL_RETURN_URL = os.getenv("STRIPE_PORTAL_RETURN_URL", "http://localhost:3000/billing/")
    STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/billing/?success=1")
    STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/billing/?cancel=1")

    TOKEN_ENCRYPTION_KEY = os.getenv("TOKEN_ENCRYPTION_KEY", "")


settings = Settings()

for _path in (
    settings.CACHE_DIR,
    settings.OUTPUT_DIR,
    settings.FOOTAGE_CACHE_DIR,
    settings.OUTPUT_VIDEOS_DIR,
    settings.OUTPUT_AUDIO_DIR,
    settings.OUTPUT_SUBTITLES_DIR,
    settings.OUTPUT_MANIFESTS_DIR,
):
    _path.mkdir(parents=True, exist_ok=True)
