"""Supabase-backed access control for Telegram subscribers."""
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _headers():
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


def _get(path, params=None):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=_headers(), params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _post(path, payload):
    headers = _headers()
    headers["Prefer"] = "return=representation"
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _patch(path, params, payload):
    headers = _headers()
    headers["Prefer"] = "return=representation"
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, params=params, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def active_users():
    return _get("users", {"status": "eq.active", "select": "telegram_id,email,telegram_username"})


def link_telegram(start_token, telegram_id, telegram_username=None, first_name=None):
    rows = _get("access_requests", {"token": f"eq.{start_token}", "select": "id,email,used", "limit": "1"})
    if not rows or rows[0].get("used"):
        return None
    req = rows[0]
    # Upsert the user by email. Pending until an admin approves them.
    existing = _get("users", {"email": f"eq.{req['email']}", "select": "id,status", "limit": "1"})
    payload = {
        "email": req["email"],
        "telegram_id": str(telegram_id),
        "telegram_username": telegram_username,
        "first_name": first_name,
        "status": existing[0]["status"] if existing else "pending",
    }
    if existing:
        result = _patch("users", {"id": f"eq.{existing[0]['id']}"}, payload)
    else:
        result = _post("users", payload)
    _patch("access_requests", {"id": f"eq.{req['id']}"}, {"used": True})
    return result[0] if result else None
