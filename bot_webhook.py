"""Local webhook handler logic; the production webhook lives in worker/worker.js.
Kept here as a reference/testable implementation for Python deployments."""
from html import escape
import config
import access_store


def handle_update(update: dict):
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    if not chat.get("id"):
        return None
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 1:
            return "Please open the access link you received, then press START again."
        user = message.get("from") or {}
        linked = access_store.link_telegram(parts[1], chat["id"], user.get("username"), user.get("first_name"))
        if not linked:
            return "❌ This access link is invalid or has already been used."
        if linked.get("status") == "active":
            return "✅ Your access is already active. You will receive SLK alerts here."
        return "🕐 Your Telegram account is linked. Your access is pending admin approval."
    if text == "/status":
        return "Use your access link to connect this Telegram account."
    return "Use the access link from the SLK website to connect your Telegram account."
