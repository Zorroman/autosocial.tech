import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the project directory, regardless of current working dir.
load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

class Config:
    FB_APP_ID = (
        os.getenv("FB_APP_ID")
        or os.getenv("FB_LOGIN_APP_ID")
        or os.getenv("FACEBOOK_APP_ID")
        or os.getenv("FACEBOOK_CLIENT_ID")
    )
    FB_APP_SECRET = (
        os.getenv("FB_APP_SECRET")
        or os.getenv("FB_LOGIN_APP_SECRET")
        or os.getenv("FACEBOOK_APP_SECRET")
        or os.getenv("FACEBOOK_CLIENT_SECRET")
    )
    REDIRECT_URI = (
        os.getenv("REDIRECT_URI")
        or os.getenv("FB_LOGIN_REDIRECT_URI")
    )
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # ← ЭТОГО НЕ ХВАТАЛО
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
