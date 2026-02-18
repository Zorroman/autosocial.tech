import os

class Config:
    FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID")
    FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
    REDIRECT_URI = os.getenv("REDIRECT_URI")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
