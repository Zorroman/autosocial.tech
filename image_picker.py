import requests
from config import Config
import random

def get_image_by_niche(niche):
    url = "https://api.pexels.com/v1/search"
    headers = {
        "Authorization": Config.PEXELS_API_KEY
    }
    params = {
        "query": niche,
        "per_page": 10,  # Получим 10 разных фото
        "page": random.randint(1, 5)  # До 80 фото в Pexels доступно
    }

    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        if data["photos"]:
            photo = random.choice(data["photos"])
            return photo["src"]["large"]
        else:
            return "https://via.placeholder.com/600x400.png?text=No+Image+Found"
    except Exception as e:
        return f"Ошибка: {str(e)}"

    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        if data["photos"]:
            return data["photos"][0]["src"]["large"]
        else:
            return "https://via.placeholder.com/600x400.png?text=No+Image+Found"
    except Exception as e:
        return f"Ошибка: {str(e)}"
