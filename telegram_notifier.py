import requests
import config
import access_store


def _send(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20)
    if not r.ok:
        print(f"Telegram send failed for {chat_id}: {r.status_code} {r.text[:300]}")
    r.raise_for_status()
    return r.json()


def send_message(text: str):
    """Broadcast to every approved user. Legacy single-chat mode is supported as fallback."""
    try:
        users = access_store.active_users()
    except Exception as exc:
        print(f"Access database unavailable: {exc}")
        legacy = getattr(config, "TELEGRAM_CHAT_ID", "")
        if legacy and not legacy.startswith("PUT_YOUR"):
            return _send(legacy, text)
        raise

    sent = 0
    for user in users:
        chat_id = user.get("telegram_id")
        if not chat_id:
            continue
        try:
            _send(chat_id, text)
            sent += 1
        except Exception as exc:
            print(f"Broadcast error for {chat_id}: {exc}")
    return {"sent": sent, "total": len(users)}
