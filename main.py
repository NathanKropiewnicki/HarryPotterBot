from flask import Flask, request, jsonify, make_response as flask_make_response
import json
import sqlite3
from datetime import datetime, date
import os
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

DB_FILE = "hogwarts.db"
HOUSES = ["gryffindor", "hufflepuff", "ravenclaw", "slytherin"]
DAILY_CHECKIN_CUTOFF_HOUR = 10  # 10 AM UTC

# ---------------------------- DB Setup ----------------------------
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

# -------------------------- Utilities -----------------------------
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
        return False  # Already checked in

    cursor.execute("UPDATE users SET last_checkin = ? WHERE user_id = ?", (today.isoformat(), user_id))
    cursor.execute("SELECT house FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        house = row[0]
        add_points(house, 5)

    conn.commit()
    conn.close()
    return True

# -------------------- Bot Framework Response ----------------------
def make_response(text, user_id="user"):
    return {
        "type": "message",
        "id": f"resp-{datetime.utcnow().timestamp()}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "from": {"id": "bot", "name": "HogwartsBot"},
        "recipient": {"id": user_id, "name": user_id},
        "conversation": {"id": f"conv-{user_id}"},
        "replyToId": "message-id",
        "channelId": "emulator"  # helps with Azure compatibility
    }

# ------------------------ Flask Routes ----------------------------
@app.route("/", methods=["GET"])
def home():
    return "Hogwarts Bot is running! 🧙‍♂️", 200

@app.route("/api/messages", methods=["POST"])
def messages():
    data = request.json
    print("✅ Message received:", json.dumps(data, indent=2))

    service_url = data.get("serviceUrl")
    conversation_id = data.get("conversation", {}).get("id")
    user_id = data.get("from", {}).get("id")

    if not (service_url and conversation_id and user_id):
        return make_response("", 200)

    reply_url = f"{service_url}/v3/conversations/{conversation_id}/activities"

    reply = {
        "type": "message",
        "text": "🧙 Hello from Hogwarts Bot!"
    }

    headers = {
        "Content-Type": "application/json"
    }

    # If using authentication: add Authorization header here

    # POST the reply back to Teams via Azure Bot Framework
    response = requests.post(reply_url, json=reply, headers=headers)
    print("🛠️ Reply status:", response.status_code, response.text)

    return make_response("", 200)



# -------------------------- Run App -------------------------------
if __name__ == "__main__":
    print("🚀 Hogwarts Bot is starting up...")
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
