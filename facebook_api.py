import time
import requests
from config import Config


def exchange_code_for_token(code, redirect_uri=None):
    # Use a stable Graph version. Keep consistent with the dialog/oauth URL (v20.0 in this app).
    url = "https://graph.facebook.com/v20.0/oauth/access_token"
    params = {
        "client_id": Config.FB_APP_ID,
        "redirect_uri": redirect_uri or Config.REDIRECT_URI,
        "client_secret": Config.FB_APP_SECRET,
        "code": code,
    }
    response = requests.get(url, params=params, timeout=20)
    try:
        data = response.json()
    except Exception:
        data = {"error": {"message": (response.text or "")[:1000], "type": "non_json_response"}}

    # Help callers surface more actionable errors without leaking secrets.
    data["_http_status"] = response.status_code
    return data


def list_pages(access_token: str, include_page_access_token: bool = False):
    """
    List Facebook Pages available to the user token, including linked Instagram business account (if any).
    Requires: pages_show_list (and often business_management).
    """
    url = "https://graph.facebook.com/v20.0/me/accounts"
    fields = "id,name,picture{url},instagram_business_account{id,username}"
    if include_page_access_token:
        fields = f"{fields},access_token,tasks"

    params = {
        "access_token": access_token,
        # "picture" is used for miniatures in UI.
        "fields": fields,
        "limit": 100,
    }
    res = requests.get(url, params=params, timeout=20).json()
    if not isinstance(res, dict):
        return {"error": {"message": "Invalid Meta response format"}}
    if res.get("error"):
        return res

    all_pages = list(res.get("data") or [])
    paging = res.get("paging") or {}
    next_url = paging.get("next")
    hops = 0
    while next_url and hops < 20:
        hops += 1
        next_res = requests.get(next_url, timeout=20).json()
        if not isinstance(next_res, dict):
            break
        if next_res.get("error"):
            return next_res
        all_pages.extend(next_res.get("data") or [])
        next_url = (next_res.get("paging") or {}).get("next")

    res["data"] = all_pages
    return res


def get_page_and_ig_id(access_token):
    url = "https://graph.facebook.com/v20.0/me/accounts"
    params = {
        "access_token": access_token,
        "fields": "id,name,picture{url},instagram_business_account{id,username}",
    }
    res = requests.get(url, params=params, timeout=20).json()

    if res.get("error"):
        return None, None, res

    if not res.get("data"):
        return None, None, res

    pages = res["data"]
    # Prefer page with linked Instagram business account.
    page = next((p for p in pages if p.get("instagram_business_account")), pages[0])
    return page["id"], page.get("instagram_business_account", {}).get("id"), res


def publish_to_facebook(page_id, access_token, image_url, caption):
    """
    Publish to a Facebook Page.
    If image_url is provided, publish as photo.
    If image_url is missing, publish as text post to /feed.
    """
    caption = caption or ""
    if image_url:
        url = f"https://graph.facebook.com/v20.0/{page_id}/photos"
        payload = {
            "url": image_url,
            "caption": caption,
            "access_token": access_token,
        }
    else:
        url = f"https://graph.facebook.com/v20.0/{page_id}/feed"
        payload = {
            "message": caption,
            "access_token": access_token,
        }
    started = time.perf_counter()
    res = requests.post(url, data=payload, timeout=30)
    data = res.json()
    if isinstance(data, dict):
        data.setdefault("_timing_ms", {})
        data["_timing_ms"]["request_ms"] = int((time.perf_counter() - started) * 1000)
    return data


def publish_to_instagram(ig_user_id, access_token, image_url, caption):
    started_total = time.perf_counter()
    timing = {}
    if not image_url:
        return {"error": "image_url is required for Instagram publishing"}

    create_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media"
    create_payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }

    started_create = time.perf_counter()
    create_res = requests.post(create_url, data=create_payload, timeout=30)
    timing["create_ms"] = int((time.perf_counter() - started_create) * 1000)
    create_data = create_res.json()
    if "id" not in create_data:
        return {"error": "Failed to create media", "details": create_data, "_timing_ms": timing}

    creation_id = create_data["id"]

    # Wait until container is ready for publish.
    status_url = f"https://graph.facebook.com/v20.0/{creation_id}"
    started_wait = time.perf_counter()
    for _ in range(8):
        status_res = requests.get(
            status_url,
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=20,
        )
        status_data = status_res.json()
        status_code = str(status_data.get("status_code") or status_data.get("status") or "").upper()
        if status_code in {"FINISHED", "PUBLISHED"}:
            break
        if status_code in {"ERROR", "EXPIRED"}:
            timing["status_wait_ms"] = int((time.perf_counter() - started_wait) * 1000)
            timing["total_ms"] = int((time.perf_counter() - started_total) * 1000)
            return {"error": "Media container error", "details": status_data, "creation_id": creation_id, "_timing_ms": timing}
        time.sleep(2)
    timing["status_wait_ms"] = int((time.perf_counter() - started_wait) * 1000)

    publish_url = f"https://graph.facebook.com/v20.0/{ig_user_id}/media_publish"
    publish_payload = {"creation_id": creation_id, "access_token": access_token}

    last_error = None
    started_publish = time.perf_counter()
    for _ in range(5):
        publish_res = requests.post(publish_url, data=publish_payload, timeout=30)
        publish_data = publish_res.json()
        err = publish_data.get("error")
        if not err and publish_data.get("id"):
            publish_data.setdefault("_timing_ms", {})
            publish_data["_timing_ms"].update(timing)
            publish_data["_timing_ms"]["publish_ms"] = int((time.perf_counter() - started_publish) * 1000)
            publish_data["_timing_ms"]["total_ms"] = int((time.perf_counter() - started_total) * 1000)
            return publish_data

        code = str((err or {}).get("code", ""))
        subcode = str((err or {}).get("error_subcode", ""))
        # Known transient response while container is still processing.
        if code == "9007" or subcode == "2207027":
            last_error = publish_data
            time.sleep(2)
            continue
        publish_data.setdefault("_timing_ms", {})
        publish_data["_timing_ms"].update(timing)
        publish_data["_timing_ms"]["publish_ms"] = int((time.perf_counter() - started_publish) * 1000)
        publish_data["_timing_ms"]["total_ms"] = int((time.perf_counter() - started_total) * 1000)
        return publish_data

    if last_error and isinstance(last_error, dict):
        last_error.setdefault("_timing_ms", {})
        last_error["_timing_ms"].update(timing)
        last_error["_timing_ms"]["publish_ms"] = int((time.perf_counter() - started_publish) * 1000)
        last_error["_timing_ms"]["total_ms"] = int((time.perf_counter() - started_total) * 1000)
        return last_error
    timing["publish_ms"] = int((time.perf_counter() - started_publish) * 1000)
    timing["total_ms"] = int((time.perf_counter() - started_total) * 1000)
    return {"error": "Failed to publish media", "creation_id": creation_id, "_timing_ms": timing}
