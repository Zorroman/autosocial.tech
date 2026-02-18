import os


class Settings:
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
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", FRONTEND_BASE_URL)
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", "")
    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}

    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_PRICE_INPUT_PER_1M = float(os.getenv("OPENAI_PRICE_INPUT_PER_1M", "0.15"))
    OPENAI_PRICE_OUTPUT_PER_1M = float(os.getenv("OPENAI_PRICE_OUTPUT_PER_1M", "0.60"))
    CREDIT_MULTIPLIER = float(os.getenv("CREDIT_MULTIPLIER", "1"))
    AVG_TOKENS_PER_POST = int(os.getenv("AVG_TOKENS_PER_POST", "1200"))
    SOFT_LIMIT_RATIO = float(os.getenv("SOFT_LIMIT_RATIO", "0.9"))
    OVERDRAFT_LIMIT = int(os.getenv("OVERDRAFT_LIMIT", "-10000"))

    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
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
