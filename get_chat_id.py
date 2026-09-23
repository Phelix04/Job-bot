"""
One-time helper to find your Telegram chat_id.

Steps:
1. Open Telegram, find your bot (search its @username), and send it
   any message, e.g. "hello".
2. Fill in your bot token below (or in config.json - this script reads
   it from config.json automatically if present).
3. Run:  python get_chat_id.py
4. Copy the chat id it prints into config.json under "telegram_chat_id".
"""
import json
import os
import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def main():
    token = None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            token = config.get("telegram_bot_token")

    if not token or "PASTE_YOUR" in token:
        token = input("Paste your bot token from BotFather: ").strip()

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    resp = requests.get(url, timeout=20)
    data = resp.json()

    if not data.get("ok"):
        print("Telegram API error:", data)
        return

    results = data.get("result", [])
    if not results:
        print(
            "No messages found yet. Send your bot a message on Telegram "
            "first (search its username and type 'hello'), then run this "
            "script again."
        )
        return

    seen_ids = set()
    for update in results:
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        chat = msg["chat"]
        if chat["id"] in seen_ids:
            continue
        seen_ids.add(chat["id"])
        name = chat.get("username") or chat.get("first_name") or "unknown"
        print(f"chat_id: {chat['id']}   (from: {name})")

    print("\nCopy the chat_id above into config.json as \"telegram_chat_id\".")


if __name__ == "__main__":
    main()
