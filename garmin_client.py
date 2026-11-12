"""
Shared helper for talking to Garmin's Personal API.
Uses only Python's built-in libraries (urllib, json, os, time) - nothing to install.
"""
import json
import os
import time
import urllib.request
import urllib.error

BASE_URL = "https://personal.connectapi.garmin.com"
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "data", "token.json")
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env.local")

TOKEN_MAX_AGE_HOURS = 20


def load_api_key():
    if not os.path.exists(ENV_PATH):
        raise RuntimeError(".env.local not found. Create it with GARMIN_PERSONAL_API_KEY=<your key>")
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GARMIN_PERSONAL_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key:
                    return key
    raise RuntimeError(
        "GARMIN_PERSONAL_API_KEY is empty in .env.local. "
        "Open the file, paste your key after the '=', and save."
    )


def _request(method, url, headers=None, data=None, timeout=30):
    req = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, body


def fetch_new_token():
    api_key = load_api_key()
    url = f"{BASE_URL}/personalapitoken-service/personal-api/personal-api-key/token"
    status, body = _request("POST", url, headers={"Authorization": f"ApiKey {api_key}"})
    if status != 200:
        raise RuntimeError(
            f"Token request failed (HTTP {status}). "
            "Your key may be missing, mistyped, or expired. "
            "Double-check GARMIN_PERSONAL_API_KEY in .env.local."
        )
    token = body.decode("utf-8").strip()
    if not token:
        raise RuntimeError("Token request succeeded but returned an empty token.")
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        json.dump({"token": token, "fetched_at": time.time()}, f)
    return token


def get_token(force_refresh=False):
    if not force_refresh and os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as f:
            saved = json.load(f)
        age_hours = (time.time() - saved["fetched_at"]) / 3600
        if age_hours < TOKEN_MAX_AGE_HOURS:
            return saved["token"]
    return fetch_new_token()


def api_get(path, params=None, retries=3):
    """GET a path under BASE_URL, with the Bearer token. Retries on 429/502/503."""
    token = get_token()
    url = f"{BASE_URL}{path}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    last_error = None
    for attempt in range(retries):
        status, body = _request("GET", url, headers={"Authorization": f"Bearer {token}"})
        if status in (200, 204):
            if not body:
                return None
            return json.loads(body)
        if status in (429, 502, 503):
            last_error = f"HTTP {status}"
            time.sleep(3 + attempt * 2)
            continue
        if status == 401:
            # token might have just expired; refresh once and retry
            token = get_token(force_refresh=True)
            continue
        if status == 500:
            # caller should handle by shrinking the request range
            raise RuntimeError("HTTP 500 - response likely too large, try a smaller range")
        raise RuntimeError(f"GET {path} failed with HTTP {status}: {body[:200]}")
    raise RuntimeError(f"GET {path} failed after {retries} retries: {last_error}")
