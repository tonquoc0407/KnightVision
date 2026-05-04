# Telegram notification entrypoint for Airflow pipeline status messages

from __future__ import annotations

import argparse
import os

import httpx


def send_telegram_message(message: str, *, token: str | None = None, chat_id: str | None = None) -> bool:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured.")
        return False

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=20,
    )
    response.raise_for_status()
    return True

def main() -> None:
    parser = argparse.ArgumentParser(description="Send a KnightVision pipeline notification.")
    parser.add_argument("--month", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--details", default="")
    args = parser.parse_args()

    message = f"KnightVision monthly pipeline {args.status} for {args.month}"
    if args.details:
        message = f"{message}\n{args.details}"
    sent = send_telegram_message(message)
    print("Telegram notification sent." if sent else message)

if __name__ == "__main__":
    main()