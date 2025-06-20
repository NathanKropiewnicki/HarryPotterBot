from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime, date, timezone
import os
import requests
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_FILE = "hogwarts.db"
HOUSES = ["gryffindor", "hufflepuff", "ravenclaw", "slytherin"]
DAILY_CHECKIN_CUTOFF_HOUR = 10  # 10 AM UTC

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            house TEXT,
            last_checkin DATE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS house_points (
            house TEXT PRIMARY KEY,
            points INTEGER DEFAULT 0
        )
    """)
    for house in HOUSES:
        cursor.execute("INSERT OR IGNORE INTO house_points (house, points) VALUES (?, ?)", (house, 0))
    conn.commit()
    conn.close()

def add_points(house, points):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE house_points SET points = points + ? WHERE house = ?", (points, house))
    conn.commit()
    conn.close()

def set_user_house(user_id, user_name, house):
    if house not in HOUSES:
        return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, user_name, house) VALUES (?, ?, ?)", (user_id, user_name, house))
    conn.commit()
    conn.close()
    return True

def get_leaderboard():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT house, points FROM house_points ORDER BY points DESC")
    leaderboard = cursor.fetchall()
    conn.close()
    return leaderboard

def handle_checkin(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    today = date.today()
    cursor.execute("SELECT last_checkin FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row and row[0] == today.isoformat():
        return False
    cursor.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (today.isoformat(), user_id))
    cursor.execute("SELECT house FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        house = row[0]
        add_points(house, 5)
    conn.commit()
    conn.close()
    return True

def get_bot_access_token():
    url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": os.environ["MICROSOFT_APP_ID"],
        "client_secret": os.environ["MICROSOFT_APP_PASSWORD"],
        "scope": "https://api.botframework.com/.default"
    }
    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]

def send_bot_reply(service_url, conversation_id, recipient, bot, reply_to_id, text):
    access_token = get_bot_access_token()
    url = f"{service_url}/v3/conversations/{conversation_id}/activities"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "type": "message",
        "from": bot,
        "recipient": recipient,
        "replyToId": reply_to_id,
        "text": text
    }
    response = requests.post(url, headers=headers, json=payload)
    print("🔁 Bot Framework reply:", response.status_code, response.text)
    return response.status_code

@app.route("/", methods=["GET"])
def home():
    return "Hogwarts Bot is running! 🧙‍♂️", 200

@app.route("/api/messages", methods=["POST"])
def messages():
    try:
        data = request.json
        print("📥 Incoming message:\n", json.dumps(data, indent=2))

        text = data.get("text", "").lower()
        user_id = data.get("from", {}).get("id", "user")
        user_name = data.get("from", {}).get("name", "wizard")
        service_url = data.get("serviceUrl")
        conversation_id = data.get("conversation", {}).get("id")
        reply_to_id = data.get("id")
        recipient = data.get("from")
        bot = data.get("recipient")

        # Default reply
        reply_text = "🧙 Hello from Hogwarts Bot!"

        if "set house" in text:
            for house in HOUSES:
                if house in text:
                    success = set_user_house(user_id, user_name, house)
                    reply_text = f"✅ {user_name}, you have been placed in {house.title()}!" if success else "⚠️ Invalid house."
                    break
            else:
                reply_text = "⚠️ Please specify a valid house."

        elif text.startswith("+") and "to" in text:
            try:
                parts = text.split(" ")
                points = int(parts[0].replace("+", ""))
                house = parts[2]
                reason = " ".join(parts[3:])
                if house in HOUSES:
                    add_points(house, points)
                    reply_text = f"✅ {points} points to {house.title()} for {reason}"
                else:
                    reply_text = "⚠️ Unknown house."
            except:
                reply_text = "⚠️ Format should be like '+10 to gryffindor for helping'"

        elif "check in" in text:
            now = datetime.utcnow()
            if now.hour >= DAILY_CHECKIN_CUTOFF_HOUR:
                reply_text = "⏰ Check-in window has closed (after 10 AM UTC)."
            else:
                did_checkin = handle_checkin(user_id)
                reply_text = (
                    f"✅ {user_name}, 5 points awarded to your house for checking in!"
                    if did_checkin else
                    "📅 You've already checked in today."
                )

        elif "leaderboard" in text:
            leaderboard = get_leaderboard()
            reply_text = "🏆 House Leaderboard:\n" + "\n".join(
                f"{i+1}. {house.title()} — {pts} pts" for i, (house, pts) in enumerate(leaderboard)
            )

        send_bot_reply(service_url, conversation_id, recipient, bot, reply_to_id, reply_text)
        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Hogwarts Bot is starting...")
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
