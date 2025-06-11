import streamlit as st
from datetime import datetime, timedelta
import pytz
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
MAX_PLAYERS = 8
MIN_PLAYERS = 5
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

# ===== Google Sheets =====
def get_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"]), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1Si8leXEZH7_bXFzDbN7gwWgBEpZ__TQ_nSlO67bGYkA")
    return {
        "current": sheet.worksheet("Current"),
        "last": sheet.worksheet("Last"),
        "reset": sheet.worksheet("ResetLog")
    }

def get_registered_players():
    sheet = get_sheets()["current"]
    rows = sheet.get_all_values()[1:]
    return [(row[0], row[1]) for row in rows if len(row) >= 2]

def register_player(name):
    now_dt = datetime.now(ISRAEL_TZ)
    timestamp = f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"
    players = get_registered_players()
    players.append((name, timestamp))
    sync_players_to_sheet(players, "current")
    return True

def unregister_player(name):
    players = get_registered_players()
    updated = [p for p in players if p[0] != name]
    sync_players_to_sheet(updated, "current")

def reset_registered():
    sync_players_to_sheet([], "current")

def sync_players_to_sheet(players, sheet_name):
    sheets = get_sheets()
    sheet = sheets[sheet_name]
    sheet.clear()
    sheet.append_row(["name", "timestamp"])
    for name, ts in players:
        sheet.append_row([name, ts])

def load_last_players_from_sheet():
    sheet = get_sheets()["last"]
    rows = sheet.get_all_values()[1:]
    return [row[0] for row in rows if len(row) >= 1]

def save_last_players(players):
    sync_players_to_sheet(players, "last")

def log_reset_time(now):
    sheets = get_sheets()
    sheet = sheets["reset"]
    sheet.append_row([now.strftime("%Y-%m-%d %H:%M")])
    sheet.update_acell("B1", now.strftime("%Y-%m-%d %H:%M"))  # שמירה של האיפוס האחרון

def get_last_reset_time():
    sheet = get_sheets()["reset"]
    try:
        value = sheet.acell("B1").value
        if value:
            return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ISRAEL_TZ)
    except:
        pass
    return None

# ===== עזר =====
def get_allowed_players():
    return json.loads(st.secrets["players"])

def get_player(name, all_players):
    for p in all_players:
        if p["name"] == name:
            return p
    return None

def get_priority_players(all_players, last_players):
    return [p["name"] for p in all_players if p["name"] not in last_players]

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
    last_reset = get_last_reset_time()
    if not last_reset:
        log_reset_time(now)
        return True
    this_friday = now.replace(hour=18, minute=0, second=0, microsecond=0)
    while this_friday.weekday() != 4:
        this_friday -= timedelta(days=1)
    if last_reset < this_friday <= now:
        log_reset_time(now)
        return True
    return False

# ===== התחלה =====
now = datetime.now(ISRAEL_TZ)
all_players = get_allowed_players()
players = get_registered_players()
registration_open = is_registration_open(now)

if is_new_registration_period(now):
    log_reset_time(now)
    save_last_players(players)
    reset_registered()
    players = []
    priority_players = get_priority_players(all_players, load_last_players_from_sheet())
    for p_name in priority_players:
        if len(players) < MAX_PLAYERS:
            now_dt = datetime.now(ISRAEL_TZ)
            hebrew_ts = f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"
            register_player(p_name)

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

priority_players = get_priority_players(all_players, load_last_players_from_sheet())
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
        is_registered = any(name == p[0] for p in players)

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
