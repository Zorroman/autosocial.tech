import requests
from config import Config

def fetch_image_url(query):
    headers = {"Authorization": Config.PEXELS_API_KEY}
    res = requests.get(
        f"https://api.pexels.com/v1/search?query={query}&per_page=1",
        headers=headers
    ).json()
    return res['photos'][0]['src']['original']
