"""
get_chat_id.py
--------------
Run this ONCE after creating your bot to find your personal chat ID.

Steps:
  1. Start your bot in Telegram (search for it, hit Start)
  2. Send any message to your bot
  3. Run:  python get_chat_id.py
  4. Copy the chat ID into your .env as CHAT_ID
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.environ["TELEGRAM_TOKEN"]

url = f"https://api.telegram.org/bot{token}/getUpdates"
resp = requests.get(url).json()

if not resp.get("result"):
    print("No messages found. Make sure you sent a message to your bot first.")
else:
    for update in resp["result"]:
        msg = update.get("message", {})
        chat = msg.get("chat", {})
        print(f"Chat ID : {chat.get('id')}")
        print(f"Name    : {chat.get('first_name')} {chat.get('last_name', '')}")
        print(f"Username: @{chat.get('username', 'N/A')}")
        print("---")
