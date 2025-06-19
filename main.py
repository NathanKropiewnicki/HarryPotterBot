from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import re
import os

app = Flask(__name__)
DB_PATH = 'hogwarts_bot.db'

HOUSES = ["gryffindor", "hufflepuff", "ravenclaw", "slytherin"]

# Ensure the database exists
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        house TEXT,
        last_checkin TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS house_points (
        house TEXT PRIMARY KEY,
        points INTEGER DEFAULT 0
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS points_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        house TEXT,
        amount INTEGER,
        reason TEXT,
        timestamp TEXT,
        source TEXT
    )""")
    for house in HOUSES:
        cur.execute("INSERT OR IGNORE INTO house_points (house, points) VALUES (?, 0)", (house,))
    conn.commit()
    conn.close()

# Helper to award points
def award_points(house, amount, reason, source, user_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE house_points SET points = points + ? WHERE house = ?", (amount, house))
    cur.execute("INSERT INTO points_log (user_id, house, amount, reason, timestamp, source) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, house, amount, reason, datetime.utcnow().isoformat(), source))
    conn.commit()
    conn.close()

# Endpoint to handle messages
@app.route('/api/messages', methods=['POST'])
def messages():
    data = request.json
    user_id = data.get("user_id")
    user_name = data.get("user_name")
    message = data.get("text", "").lower()
    now = datetime.utcnow()

    if message.startswith("set house"):
        selected_house = message.split()[-1]
        if selected_house in HOUSES:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO users (id, name, house, last_checkin) VALUES (?, ?, ?, ?)",
                        (user_id, user_name, selected_house, None))
            conn.commit()
            conn.close()
            return jsonify({"text": f"✅ {user_name}, you have been placed in {selected_house.title()}!"})
        return jsonify({"text": "Invalid house. Choose from Gryffindor, Hufflepuff, Ravenclaw, or Slytherin."})

    if "+" in message and "to" in message:
        try:
            match = re.search(r"(\+\d+).*to (gryffindor|hufflepuff|ravenclaw|slytherin)(.*)?", message)
            if match:
                points = int(match.group(1))
                house = match.group(2)
                reason = match.group(3).strip() or "No reason"
                award_points(house, points, reason, "manual", user_id)
                return jsonify({"text": f"✅ {points} points to {house.title()} for {reason}"})
        except:
            pass

    if "leaderboard" in message:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT house, points FROM house_points ORDER BY points DESC")
        rows = cur.fetchall()
        leaderboard = "\n".join([f"{i+1}. {row[0].title()} — {row[1]} pts" for i, row in enumerate(rows)])
        return jsonify({"text": f"🏆 House Leaderboard\n{leaderboard}"})

    if "check in" in message and now.hour < 15:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT house, last_checkin FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            house = row[0]
            last_checkin = row[1]
            today = now.date().isoformat()
            if last_checkin != today:
                cur.execute("UPDATE users SET last_checkin = ? WHERE id = ?", (today, user_id))
                award_points(house, 5, "Daily check-in", "checkin", user_id)
                conn.commit()
                return jsonify({"text": f"✅ Good morning, {user_name}! 5 points to {house.title()} for checking in."})
            else:
                return jsonify({"text": "You've already checked in today."})
        return jsonify({"text": "Set your house first using 'set house [house]' command."})

    return jsonify({"text": "I don't understand that command yet."})

# Cron job endpoint to reset points and announce winner
@app.route('/cron/reset_monthly', methods=['POST'])
def reset_monthly():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT house, points FROM house_points ORDER BY points DESC LIMIT 1")
    winner = cur.fetchone()
    cur.execute("UPDATE house_points SET points = 0")
    conn.commit()
    conn.close()
    winner_text = f"🎉 The House Cup goes to *{winner[0].title()}* with {winner[1]} points! Points have been reset."
    return jsonify({"text": winner_text})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
