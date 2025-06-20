from flask import Flask, request, make_response as flask_make_response
import sqlite3
from datetime import datetime, date, timezone
import os
import json
from flask_cors import CORS

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
    try:
        data = request.json
        print("✅ Received POST /api/messages")
        print("Incoming message:", data)

        # Grab info from Bot Framework payload
        user_id = data.get("from", {}).get("id", "user")
        user_name = data.get("from", {}).get("name", "wizard")

        response = {
            "type": "message",
            "text": f"Hello {user_name}, this is a test reply from your Hogwarts bot!",
            "from": {"id": "bot", "name": "HogwartsBot"},
            "recipient": {"id": user_id, "name": user_name},
            "conversation": data.get("conversation", {"id": "conv-id"}),
            "replyToId": data.get("id"),
            "channelId": data.get("channelId", "emulator")
        }

        return flask_make_response(json.dumps(response), 200, {"Content-Type": "application/json"})

    except Exception as e:
        print("Error:", e)
        return flask_make_response(json.dumps({
            "type": "message",
            "text": "⚠️ An error occurred in the bot.",
            "from": {"id": "bot"},
            "recipient": {"id": "user"},
            "conversation": {"id": "conv-id"},
        }), 200, {"Content-Type": "application/json"})


# -------------------------- Run App -------------------------------
if __name__ == "__main__":
    print("🚀 Hogwarts Bot is starting up...")
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
