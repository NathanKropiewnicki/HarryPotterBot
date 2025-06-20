#  Hogwarts House Bot for Microsoft Teams

This is a fun, interactive AI bot designed for **Microsoft Teams**, inspired by the **Harry Potter universe**. It allows users to:

- Get sorted into one of the four Hogwarts houses
- Earn points via daily check-ins
- Manually award house points using commands
- View the live house points leaderboard
- Automatically reset points and declare a House Cup winner monthly

Deployed using **Flask**, hosted on **Render**, and integrated with **Azure Bot Services**.

---

##  Features

-  House assignment via `set house [house name]`
-  Daily check-in system awarding 5 points (before 10 AM UTC only)
-  Manual point awards: `+10 to gryffindor for helping a teammate`
-  Leaderboard display: `show leaderboard`
-  Monthly House Cup announcement and points reset
-  Flask backend with SQLite database for persistence

---

##  Deployment Overview

###  Tech Stack

- Python 3 (Flask)
- SQLite (for persistence)
- Azure Bot Channels Registration
- Hosted on Render

---

##  Installation & Local Development

### 1. Clone the Repo

```bash
git clone https://github.com/your-username/hogwarts-bot.git
cd hogwarts-bot
