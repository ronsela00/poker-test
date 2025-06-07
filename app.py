import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pytz
import os
import json

# ===== הגדרות =====
weekday_hebrew = {
    'Sunday': 'ראשון',
    'Monday': 'שני',
    'Tuesday': 'שלישי',
    'Wednesday': 'רביעי',
    'Thursday': 'חמישי',
    'Friday': 'שישי',
    'Saturday': 'שבת'
}
DB_FILE = "players.db"
LAST_RESET_FILE = "last_reset.txt"
LAST_PLAYERS_FILE = "last_players.txt"
MAX_PLAYERS = 8
MIN_PLAYERS = 5
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

# ===== פונקציות מסד נתונים =====
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS registered (
            name TEXT PRIMARY KEY,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def register_player(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        now_dt = datetime.now(ISRAEL_TZ)
        timestamp = f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"
        c.execute("INSERT INTO registered (name, timestamp) VALUES (?, ?)", (name, timestamp))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def unregister_player(name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM registered WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def get_registered_players():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT name, timestamp FROM registered")
    players = c.fetchall()
    conn.close()
    return players

def reset_registered():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM registered")
    conn.commit()
    conn.close()

# ===== ניהול תיעוד שחקנים =====
def save_last_players(players):
    with open(LAST_PLAYERS_FILE, "w") as f:
        for name, _ in players:
            f.write(name + "\n")

def load_last_players():
    if not os.path.exists(LAST_PLAYERS_FILE):
        return []
    with open(LAST_PLAYERS_FILE, "r") as f:
        return [line.strip() for line in f]

def get_priority_players(all_players, last_players):
    return [p["name"] for p in all_players if p["name"] not in last_players]

# ===== פונקציות עזר =====
def get_allowed_players():
    return json.loads(st.secrets["players"])

def get_player(name, all_players):
    for p in all_players:
        if p["name"] == name:
            return p
    return None

def is_registration_open(now):
    weekday = now.weekday()
    hour = now.hour
    if weekday == 4 and hour >= 18:
        return True
    if weekday == 5 or weekday == 6:
        return True
    if weekday == 0 and hour < 22:
        return True
    return False

def is_new_registration_period(now):
    if not os.path.exists(LAST_RESET_FILE):
        with open(LAST_RESET_FILE, "w") as f:
            f.write(now.strftime("%Y-%m-%d %H:%M"))
        return True
    try:
        with open(LAST_RESET_FILE, "r") as f:
            last_reset_str = f.read().strip()
            last_reset = datetime.strptime(last_reset_str, "%Y-%m-%d %H:%M")
    except ValueError:
        with open(LAST_RESET_FILE, "w") as f:
            f.write(now.strftime("%Y-%m-%d %H:%M"))
        return True
    last_reset = last_reset.replace(tzinfo=now.tzinfo)
    this_friday = now.replace(hour=18, minute=0, second=0, microsecond=0)
    while this_friday.weekday() != 4:
        this_friday -= timedelta(days=1)
    if last_reset < this_friday <= now:
        with open(LAST_RESET_FILE, "w") as f:
            f.write(now.strftime("%Y-%m-%d %H:%M"))
        return True
    return False

# ===== התחלה =====
init_db()
now = datetime.now(ISRAEL_TZ)
all_players = get_allowed_players()
players = get_registered_players()
registration_open = is_registration_open(now)

if is_new_registration_period(now):
    save_last_players(players)
    reset_registered()
    players = []
    priority_players = get_priority_players(all_players, load_last_players())
    for p_name in priority_players:
        if len(players) < MAX_PLAYERS:
            if register_player(p_name):
                now_dt = datetime.now(ISRAEL_TZ)
                hebrew_ts = f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"
                players.append((p_name, hebrew_ts))

# ===== ממשק =====
st.title("\U0001F0CF\U0001F4B0 טורניר הפוקר השבועי")

if registration_open:
    st.subheader("\U0001F4E2 מצב נוכחי:")
    if len(players) < MIN_PLAYERS:
        st.warning("\u26A0\ufe0f אין מספיק שחקנים עדיין. אין משחק כרגע.")
    elif len(players) == 5:
        st.info("\U0001F680 יאללה, אתה האחרון לסגור לנו את הפינה!")
    elif len(players) == 7:
        st.info("\u23F3 תמהר כי נשאר מקום אחרון!")

st.subheader("👥 שחקנים רשומים:")
if players:
    for i, (name, ts) in enumerate(players, start=1):
        if i <= 7:
            st.write(f"{i}. {name} – {ts}")
        elif i == 8:
            st.markdown(f"<div style='background-color:#fff3cd;padding:5px;border-radius:5px;color:#856404;'><b>{i}. {name} (מזמין) – {ts}</b></div>", unsafe_allow_html=True)
else:
    st.info("אין נרשמים עדיין.")

if registration_open:
    st.markdown("<div style='background-color:#d4edda;padding:10px;border-radius:5px;color:#155724;'>\u2705 ההרשמה פתוחה! ניתן להירשם ולהסיר את עצמך.</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background-color:#f8d7da;padding:10px;border-radius:5px;color:#721c24;'>\u274C ההרשמה סגורה כרגע.</div>", unsafe_allow_html=True)

priority_players = get_priority_players(all_players, load_last_players())
if registration_open and priority_players:
    st.markdown("\U0001F3AF <b>שחקנים שפספסו בפעם הקודמת:</b>", unsafe_allow_html=True)
    for p in priority_players:
        st.write(f"– {p}")

st.markdown("---")
st.header("\U0001F4CA טופס פעולה")

name = st.text_input("שם משתמש")
code = st.text_input("קוד אישי", type="password")
action = st.radio("בחר פעולה", ["להירשם למשחק", "להסיר את עצמי"])

if st.button("שלח"):
    if not name.strip() or not code.strip():
        st.warning("יש להזין שם וקוד.")
    else:
        allowed_player = get_player(name, all_players)
        is_registered = name in [p[0] for p in players]

        if action == "להירשם למשחק":
            if not registration_open:
                st.error("ההרשמה סגורה.")
            elif not allowed_player:
                st.error("שחקן לא קיים ברשימה הקבועה.")
            elif allowed_player["code"] != code:
                st.error("קוד אישי שגוי.")
            elif is_registered:
                st.info("כבר נרשמת.")
            elif len(players) >= MAX_PLAYERS:
                st.error("המשחק מלא.")
            else:
                if register_player(name):
                    st.success(f"{name} נרשמת בהצלחה!")
                else:
                    st.error("שגיאה בהרשמה.")

        elif action == "להסיר את עצמי":
            if not registration_open:
                st.warning("לא ניתן להסיר את עצמך כשההרשמה סגורה.")
            elif not allowed_player or allowed_player["code"] != code:
                st.error("שם או קוד שגויים.")
            elif not is_registered:
                st.info("אתה לא רשום כרגע.")
            else:
                unregister_player(name)
                st.success("הוסרת מהרשימה.")
