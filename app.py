# ===== קוד מלא כולל הרשמה ספונטנית =====
import streamlit as st
from datetime import datetime, timedelta
import pytz
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ===== הגדרות כלליות =====
weekday_hebrew = {
    'Sunday': 'ראשון', 'Monday': 'שני', 'Tuesday': 'שלישי',
    'Wednesday': 'רביעי', 'Thursday': 'חמישי',
    'Friday': 'שישי', 'Saturday': 'שבת'
}
MAX_PLAYERS = 8
MIN_PLAYERS = 5
ISRAEL_TZ = pytz.timezone("Asia/Jerusalem")

# ===== הגדרות גליונות =====
def get_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"]), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1Si8leXEZH7_bXFzDbN7gwWgBEpZ__TQ_nSlO67bGYkA")
    return {
        "current": sheet.worksheet("Current"),
        "last": sheet.worksheet("Last"),
        "reset": sheet.worksheet("ResetLog"),
        "spontaneous": sheet.worksheet("Spontaneous")
    }

def sync_players_to_sheet(players, sheet_name):
    sheet = get_sheets()[sheet_name]
    sheet.clear()
    sheet.append_row(["name", "timestamp"])
    for name, ts in players:
        sheet.append_row([name, ts])

def get_registered_players_from_sheet(sheet_name):
    sheet = get_sheets()[sheet_name]
    rows = sheet.get_all_values()[1:]
    return [(row[0], row[1]) for row in rows if len(row) >= 2]

# ===== הרשמה וניהול =====
def register_player(name, spontaneous=False):
    now_dt = datetime.now(ISRAEL_TZ)
    timestamp = f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"
    sheet_name = "spontaneous" if spontaneous else "current"
    players = get_registered_players_from_sheet(sheet_name)
    players.append((name, timestamp))
    sync_players_to_sheet(players, sheet_name)
    return True

def unregister_player(name, spontaneous=False):
    sheet_name = "spontaneous" if spontaneous else "current"
    players = get_registered_players_from_sheet(sheet_name)
    updated = [p for p in players if p[0] != name]
    sync_players_to_sheet(updated, sheet_name)

def reset_registered():
    sync_players_to_sheet([], "current")

def load_last_players_from_sheet():
    return [row[0] for row in get_registered_players_from_sheet("last")]

def save_last_players(players):
    sync_players_to_sheet(players, "last")

def log_reset_time(now):
    sheet = get_sheets()["reset"]
    sheet.append_row([now.strftime("%Y-%m-%d %H:%M")])
    sheet.update_acell("B1", now.strftime("%Y-%m-%d %H:%M"))

def get_last_reset_time():
    sheet = get_sheets()["reset"]
    try:
        value = sheet.acell("B1").value
        if value:
            return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ISRAEL_TZ)
    except:
        pass
    return None

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
    if weekday in [5, 6]:
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
registration_open = is_registration_open(now)

if is_new_registration_period(now):
    log_reset_time(now)
    save_last_players(get_registered_players_from_sheet("current"))
    reset_registered()
    priority_players = get_priority_players(all_players, load_last_players_from_sheet())
    for p_name in priority_players:
        if len(get_registered_players_from_sheet("current")) < MAX_PLAYERS:
            register_player(p_name)

# ===== Streamlit UI =====
st.session_state.setdefault("spontaneous_mode", False)
st.title("\U0001F0CF\U0001F4B0 טורניר הפוקר השבועי")

if st.button("✨ פתח רישום ספונטני"):
    st.session_state["spontaneous_mode"] = True
    sheets = get_sheets()
    sheets["spontaneous"].clear()
    now_dt = datetime.now(ISRAEL_TZ)
    starter = st.text_input("מי פתח את ההרשמה?", key="starter_name")
    if starter:
        sheets["spontaneous"].append_row([f"{starter} (פותח)", f"{weekday_hebrew[now_dt.strftime('%A')]} {now_dt.strftime('%H:%M')}"])

spontaneous = st.session_state["spontaneous_mode"]
sheet_name = "spontaneous" if spontaneous else "current"
players = get_registered_players_from_sheet(sheet_name)

if registration_open:
    st.subheader("\U0001F4E2 מצב נוכחי:")
    if len(players) < MIN_PLAYERS:
        st.warning("\u26A0\ufe0f אין מספיק שחקנים עדיין. אין משחק כרגע.")
    elif len(players) == 5:
        st.info("\U0001F680 יאללה, אתה האחרון לסגור לנו את הפינה!")
    elif len(players) == 7:
        st.info("\u23F3 תמהר כי נשאר מקום אחרון!")

st.subheader("⭐ הרשמה ספונטנית פעילה:" if spontaneous else "👥 שחקנים רשומים:")
if players:
    for i, (name, ts) in enumerate(players, start=1):
        if "(פותח)" in name:
            st.markdown(f"<div style='background-color:#e8f0fe;padding:6px;border-radius:5px;'><b>⭐ {name} – {ts}</b></div>", unsafe_allow_html=True)
        else:
            st.write(f"{i}. {name} – {ts}")
else:
    st.info("אין נרשמים עדיין.")

if registration_open:
    st.markdown("<div style='background-color:#d4edda;padding:10px;border-radius:5px;color:#155724;'>\u2705 ההרשמה פתוחה! ניתן להירשם ולהסיר את עצמך.</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background-color:#f8d7da;padding:10px;border-radius:5px;color:#721c24;'>\u274C ההרשמה סגורה כרגע.</div>", unsafe_allow_html=True)

if not spontaneous:
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
            elif not spontaneous and len(players) >= MAX_PLAYERS:
                st.error("המשחק מלא.")
            else:
                if register_player(name, spontaneous=spontaneous):
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
                unregister_player(name, spontaneous=spontaneous)
                st.success("הוסרת מהרשימה.")