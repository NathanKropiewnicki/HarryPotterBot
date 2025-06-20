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

        text = data.get("text", "").lower()
        user_id = data.get("from", {}).get("id", "user")
        user_name = data.get("from", {}).get("name", "wizard")

        if "set house" in text:
            for house in HOUSES:
                if house in text:
                    success = set_user_house(user_id, user_name, house)
                    if success:
                        return flask_make_response(json.dumps(make_response(f"✅ {user_name}, you have been placed in {house.title()}!", user_id)), 200, {"Content-Type": "application/json"})
            return flask_make_response(json.dumps(make_response("⚠️ Please specify a valid house.", user_id)), 200, {"Content-Type": "application/json"})

        elif text.startswith("+") and "to" in text:
            try:
                parts = text.split(" ")
                points = int(parts[0].replace("+", ""))
                house = parts[2]
                reason = " ".join(parts[3:])
                if house in HOUSES:
                    add_points(house, points)
                    return flask_make_response(json.dumps(make_response(f"✅ {points} points to {house.title()} for {reason}", user_id)), 200, {"Content-Type": "application/json"})
                else:
                    return flask_make_response(json.dumps(make_response("⚠️ Unknown house.", user_id)), 200, {"Content-Type": "application/json"})
            except:
                return flask_make_response(json.dumps(make_response("⚠️ Format should be like '+10 to gryffindor for helping'", user_id)), 200, {"Content-Type": "application/json"})

        elif "check in" in text:
            now = datetime.utcnow()
            if now.hour >= DAILY_CHECKIN_CUTOFF_HOUR:
                return flask_make_response(json.dumps(make_response("⏰ Check-in window has closed (after 10 AM UTC).", user_id)), 200, {"Content-Type": "application/json"})
            did_checkin = handle_checkin(user_id)
            if did_checkin:
                return flask_make_response(json.dumps(make_response(f"✅ {user_name}, 5 points awarded to your house for checking in!", user_id)), 200, {"Content-Type": "application/json"})
            else:
                return flask_make_response(json.dumps(make_response("📅 You've already checked in today.", user_id)), 200, {"Content-Type": "application/json"})

        elif "leaderboard" in text or "show leaderboard" in text:
            leaderboard = get_leaderboard()
            message = "🏆 House Leaderboard:\n"
            for i, (house, pts) in enumerate(leaderboard, start=1):
                message += f"{i}. {house.title()} — {pts} pts\n"
            return flask_make_response(json.dumps(make_response(message, user_id)), 200, {"Content-Type": "application/json"})

        # Default fallback
        return flask_make_response(json.dumps(make_response(
            "❓ I didn't understand that. Try:\n"
            "- set house gryffindor\n"
            "- +10 to ravenclaw for creativity\n"
            "- check in\n"
            "- show leaderboard", user_id)), 200, {"Content-Type": "application/json"})

    except Exception as e:
        print("Error:", e)
        return flask_make_response(json.dumps(make_response("⚠️ An error occurred. Please try again later.", "user")), 200, {"Content-Type": "application/json"})

# -------------------------- Run App -------------------------------
if __name__ == "__main__":
    print("🚀 Hogwarts Bot is starting up...")
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
