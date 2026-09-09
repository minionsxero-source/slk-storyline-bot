import requests
import config
import access_store


def _send(chat_id: str, text: str):
    """
    Send one Telegram message.

    Raises an exception if Telegram rejects the message or the request fails.
    """
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    r = requests.post(
        url,
        json=payload,
        timeout=20,
    )

    if not r.ok:
        print(
            f"Telegram send failed for {chat_id}: "
            f"{r.status_code} {r.text[:300]}"
        )

    r.raise_for_status()

    return r.json()


def send_message(text: str):
    """
    Broadcast a message to every approved/active user.

    Reliability rules:
    1. If the access database is unavailable, fail unless a valid
       legacy TELEGRAM_CHAT_ID is configured.
    2. If there are zero active users, fail the scan instead of
       silently reporting success.
    3. Continue sending if one user's Telegram delivery fails.
    4. If every delivery fails, fail the scan.
    5. Return delivery statistics when at least one message succeeds.
    """

    # ---------------------------------------------------------
    # Get active users
    # ---------------------------------------------------------
    try:
        users = access_store.active_users()

    except Exception as exc:
        print(f"Access database unavailable: {exc}")

        # Legacy single-chat fallback
        legacy = getattr(config, "TELEGRAM_CHAT_ID", "")

        if legacy and not legacy.startswith("PUT_YOUR"):
            print("Using legacy TELEGRAM_CHAT_ID fallback.")
            return _send(legacy, text)

        # No fallback available -> workflow must fail
        raise RuntimeError(
            "Unable to read active users from access database "
            "and no valid TELEGRAM_CHAT_ID fallback is configured."
        ) from exc

    # ---------------------------------------------------------
    # Make sure active users actually exist
    # ---------------------------------------------------------
    if not users:
        raise RuntimeError(
            "No active SLK users found. "
            "Scanner will not report success because nobody can receive alerts."
        )

    sent = 0
    failed = 0
    skipped = 0

    failures = []

    # ---------------------------------------------------------
    # Broadcast
    # ---------------------------------------------------------
    for user in users:

        chat_id = user.get("telegram_id")

        if not chat_id:
            skipped += 1

            identifier = (
                user.get("email")
                or user.get("telegram_username")
                or "unknown-user"
            )

            print(
                f"Skipping active user without telegram_id: {identifier}"
            )

            continue

        try:
            _send(chat_id, text)

            sent += 1

            print(
                f"Telegram delivered successfully to {chat_id}"
            )

        except Exception as exc:
            failed += 1

            failures.append(
                {
                    "chat_id": str(chat_id),
                    "error": str(exc),
                }
            )

            print(
                f"Broadcast error for {chat_id}: {exc}"
            )

    # ---------------------------------------------------------
    # Delivery summary
    # ---------------------------------------------------------
    total = len(users)

    print(
        f"Telegram broadcast complete: "
        f"sent={sent}, failed={failed}, skipped={skipped}, total={total}"
    )

    # ---------------------------------------------------------
    # Critical reliability check
    # ---------------------------------------------------------
    #
    # If active users exist but none received the message,
    # the GitHub Action must fail.
    #
    if sent == 0:
        error_details = "; ".join(
            f"{item['chat_id']}: {item['error']}"
            for item in failures
        )

        raise RuntimeError(
            "Telegram broadcast failed for every active user. "
            f"Failures: {error_details}"
        )

    # ---------------------------------------------------------
    # Partial failure is allowed
    # ---------------------------------------------------------
    #
    # Example:
    # 10 active users
    # 9 received message
    # 1 failed
    #
    # The scanner should still succeed because the alert was
    # delivered to the majority of users.
    #
    if failed:
        print(
            f"WARNING: {failed} of {total} active users "
            f"did not receive the Telegram message."
        )

    return {
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "total": total,
    }
