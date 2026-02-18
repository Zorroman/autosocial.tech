import requests
from config import Config

def get_access_token(code):
    url = f"https://graph.facebook.com/v18.0/oauth/access_token"
    params = {
        "client_id": Config.FACEBOOK_APP_ID,
        "redirect_uri": Config.REDIRECT_URI,
        "client_secret": Config.FACEBOOK_APP_SECRET,
        "code": code
    }
    res = requests.get(url, params=params).json()
    access_token = res['access_token']

    # Получаем список страниц
    page_info = requests.get(
        f"https://graph.facebook.com/me/accounts",
        params={"access_token": access_token}
    ).json()

    page_id = page_info['data'][0]['id']
    ig_id = page_info['data'][0]['instagram_business_account']['id']

    return {
        "access_token": access_token,
        "page_id": page_id,
        "ig_user_id": ig_id
    }

def publish_to_instagram(access_token, ig_user_id, caption, image_url):
    # Step 1: Create media object
    create_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    res1 = requests.post(create_url, data={
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token
    }).json()

    creation_id = res1['id']

    # Step 2: Publish media object
    publish_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
    res2 = requests.post(publish_url, data={
        "creation_id": creation_id,
        "access_token": access_token
    }).json()

    return res2
