"""SideQuest gamification: XP with a daily cap, daily quests, streaks and color themes.

Put this file in backend/ next to database.py.

It keeps everything in its OWN tables (xp_events, gamification_meta) and the shared user_prefs table,
so database.py does not need to change. It only reads the tasks table.

How XP works
  * Finishing a task gives XP by priority (low 10, medium 20, high 30).
  * Task XP is capped per day (DAILY_TASK_XP_CAP), so splitting one big task into
    many tiny ones can't be used to farm XP.
  * Each task pays out only ONCE, ever. Un-ticking and re-ticking it earns nothing.
  * Each daily quest you finish pays QUEST_XP on top. Quest XP is not part of the cap.
  * Levels: every XP_PER_LEVEL XP is one level.
"""
from datetime import date, datetime, timedelta

from backend.database import get_db_connection, table_columns, table_exists

# ---------- Settings you can tweak ----------
PRIORITY_XP = {"low": 10, "medium": 20, "high": 30}
DAILY_TASK_XP_CAP = 100       # most XP that finishing tasks can give in one day
QUEST_XP = 10                 # XP for each daily quest
QUESTS_PER_DAY = 3
XP_PER_LEVEL = 100

# True  = every theme is available from the start.
# False = you start with the default theme and unlock one more every 5 levels
#         (see "unlock_level" on each theme below).
UNLOCK_ALL_THEMES = False


# ---------- Daily quest templates ----------
# {n} is the goal number, {s} becomes "s" when n is more than 1.
# Each day 3 different templates are picked by rotation (see quests_for).
QUEST_TEMPLATES = [
    {"key": "any",     "text": "Complete {n} task{s} today",                          "options": [1, 2, 3]},
    {"key": "medium",  "text": "Complete {n} medium-priority task{s} today",          "options": [1, 2], "priority": "medium"},
    {"key": "high",    "text": "Complete {n} high-priority task{s} today",            "options": [1],    "priority": "high"},
    {"key": "low",     "text": "Complete {n} low-priority task{s} today",             "options": [1, 2], "priority": "low"},
    {"key": "add",     "text": "Add {n} new task{s} today",                           "options": [1, 2]},
    {"key": "ontime",  "text": "Finish {n} task{s} before the deadline",              "options": [1, 2]},
    {"key": "variety", "text": "Complete tasks from {n} different categories today",  "options": [2]},
]


# ---------- Color themes (just CSS variables) ----------
DEFAULT_THEME = "indigo"

THEMES = [
    {"key": "indigo", "name": "Indigo", "unlock_level": 1,
     "vars": {"primary": "#4f46e5", "primary-dark": "#4338ca", "bg": "#f5f6fa", "border": "#e5e7ee"}},
    {"key": "ocean", "name": "Ocean", "unlock_level": 5,
     "vars": {"primary": "#0284c7", "primary-dark": "#0369a1", "bg": "#f1f7fb", "border": "#dae6ef"}},
    {"key": "forest", "name": "Forest", "unlock_level": 10,
     "vars": {"primary": "#15803d", "primary-dark": "#166534", "bg": "#f2f8f4", "border": "#dbeadf"}},
    {"key": "sunset", "name": "Sunset", "unlock_level": 15,
     "vars": {"primary": "#ea580c", "primary-dark": "#c2410c", "bg": "#fcf6f1", "border": "#f0e1d5"}},
    {"key": "rose", "name": "Rose", "unlock_level": 20,
     "vars": {"primary": "#db2777", "primary-dark": "#be185d", "bg": "#fcf3f7", "border": "#f1dae4"}},
    {"key": "midnight", "name": "Midnight", "unlock_level": 25, "dark": True,
     "vars": {"primary": "#818cf8", "primary-dark": "#6366f1", "bg": "#0f1220", "panel": "#181b2e",
              "border": "#2a2f4a", "text": "#e8eaf6", "text-muted": "#9aa0c0",
              "danger": "#f87171", "success": "#34d399"}},
]
THEMES_BY_KEY = {t["key"]: t for t in THEMES}


# ---------- Helpers ----------

def _today():
    """Today's date. A function so tests can pretend it's another day."""
    return date.today()


def _now():
    return datetime.now()


def init():
    """Create the tables (safe to run every start) and give existing completed tasks their XP once."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS xp_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,              -- 'task' or 'quest'
            ref TEXT NOT NULL,               -- task id, or "<day>:<quest slot>"
            xp INTEGER NOT NULL,
            day TEXT NOT NULL,               -- YYYY-MM-DD ('legacy' for XP given for old tasks)
            priority TEXT,
            category TEXT,
            on_time INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE (user_id, kind, ref)
        )
    """)
    # Per-user settings live in ONE key/value table (user_prefs, shared with preferences.py).
    # The theme is stored there as key 'theme'. It used to have its own user_settings table:
    # copy those rows over once, then drop the old table.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_prefs ("
        " user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,"
        " PRIMARY KEY (user_id, key))"
    )
    if table_exists(conn, "user_settings"):
        conn.execute(
            "INSERT OR IGNORE INTO user_prefs (user_id, key, value) "
            "SELECT user_id, 'theme', theme FROM user_settings"
        )
        conn.execute("DROP TABLE user_settings")
    conn.execute("CREATE TABLE IF NOT EXISTS gamification_meta (key TEXT PRIMARY KEY, value TEXT)")

    # One-time: tasks finished before this feature existed keep the XP they were worth.
    if not conn.execute("SELECT 1 FROM gamification_meta WHERE key = 'xp_backfill'").fetchone():
        columns = table_columns(conn, "tasks")
        where = "is_completed = 1 AND user_id IS NOT NULL"
        if "list_id" in columns:
            where += " AND list_id IS NULL"          # personal tasks only
        conn.execute(
            f"""INSERT OR IGNORE INTO xp_events (user_id, kind, ref, xp, day, priority, category, on_time)
                SELECT user_id, 'task', CAST(id AS TEXT),
                       CASE priority WHEN 'high' THEN ? WHEN 'medium' THEN ? ELSE ? END,
                       'legacy', priority, category, 0
                FROM tasks WHERE {where}""",
            (PRIORITY_XP["high"], PRIORITY_XP["medium"], PRIORITY_XP["low"]),
        )
        conn.execute("INSERT INTO gamification_meta (key, value) VALUES ('xp_backfill', 'done')")
    conn.commit()
    conn.close()


def _total(conn, user_id):
    return conn.execute("SELECT COALESCE(SUM(xp), 0) FROM xp_events WHERE user_id = ?", (user_id,)).fetchone()[0]


def level_info(total_xp):
    return {
        "level": total_xp // XP_PER_LEVEL + 1,
        "total_xp": total_xp,
        "xp_in_level": total_xp % XP_PER_LEVEL,
        "xp_per_level": XP_PER_LEVEL,
    }


def _task_xp_today(conn, user_id, day):
    return conn.execute(
        "SELECT COALESCE(SUM(xp), 0) FROM xp_events WHERE user_id = ? AND kind = 'task' AND day = ?",
        (user_id, day),
    ).fetchone()[0]


# ---------- Daily quests ----------

def quests_for(day):
    """The 3 quests for a date. Same for everyone, and they rotate: a different
    set of templates every day, with the goal number also rotating."""
    d = day.toordinal()
    quests = []
    for slot in range(QUESTS_PER_DAY):
        index = (d * QUESTS_PER_DAY + slot) % len(QUEST_TEMPLATES)    # 3 consecutive -> always 3 different
        template = QUEST_TEMPLATES[index]
        goal = template["options"][(d + index) % len(template["options"])]
        quests.append({
            "slot": slot,
            "key": template["key"],
            "priority": template.get("priority"),
            "goal": goal,
            "text": template["text"].format(n=goal, s="" if goal == 1 else "s"),
        })
    return quests


def _progress(conn, user_id, day_iso, quest):
    key = quest["key"]
    if key in ("any", "medium", "high", "low"):
        sql = "SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND kind = 'task' AND day = ?"
        params = [user_id, day_iso]
        if quest["priority"]:
            sql += " AND priority = ?"
            params.append(quest["priority"])
    elif key == "add":
        sql = "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND substr(created_at, 1, 10) = ?"
        params = [user_id, day_iso]
    elif key == "ontime":
        sql = "SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND kind = 'task' AND day = ? AND on_time = 1"
        params = [user_id, day_iso]
    elif key == "variety":
        sql = "SELECT COUNT(DISTINCT category) FROM xp_events WHERE user_id = ? AND kind = 'task' AND day = ?"
        params = [user_id, day_iso]
    else:
        return 0
    return conn.execute(sql, params).fetchone()[0]


def _claimed_slots(conn, user_id, day_iso):
    rows = conn.execute(
        "SELECT ref FROM xp_events WHERE user_id = ? AND kind = 'quest' AND day = ?", (user_id, day_iso)
    ).fetchall()
    return {int(r["ref"].split(":")[1]) for r in rows}


def _streaks(conn, user_id):
    """(current, best). A day counts when all of that day's quests were finished."""
    rows = conn.execute(
        "SELECT day FROM xp_events WHERE user_id = ? AND kind = 'quest' GROUP BY day HAVING COUNT(*) >= ?",
        (user_id, QUESTS_PER_DAY),
    ).fetchall()
    days = {date.fromisoformat(r["day"]) for r in rows}

    today = _today()
    cursor = today if today in days else today - timedelta(days=1)   # today may still be in progress
    current = 0
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)

    best = run = 0
    previous = None
    for d in sorted(days):
        run = run + 1 if previous is not None and d - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = d
    return current, best


def _claim_new_quests(conn, user_id):
    """Pay out any of today's quests that are now finished. Returns messages."""
    today = _today()
    day_iso = today.isoformat()
    claimed = _claimed_slots(conn, user_id, day_iso)
    newly = []
    for quest in quests_for(today):
        if quest["slot"] in claimed:
            continue
        if _progress(conn, user_id, day_iso, quest) >= quest["goal"]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO xp_events (user_id, kind, ref, xp, day) VALUES (?, 'quest', ?, ?, ?)",
                (user_id, f"{day_iso}:{quest['slot']}", QUEST_XP, day_iso),
            )
            if cur.rowcount:
                newly.append(quest)

    messages = [f"Daily quest complete: {q['text']} +{QUEST_XP} XP" for q in newly]
    if newly and len(claimed) + len(newly) >= QUESTS_PER_DAY:
        current, _best = _streaks(conn, user_id)
        messages.append(f"All daily quests done! Your streak is now {current} day{'' if current == 1 else 's'}.")
    return messages


def _level_messages(before_total, after_total):
    before = level_info(before_total)["level"]
    after = level_info(after_total)["level"]
    messages = []
    if after > before:
        messages.append(f"Level up! You are now level {after}.")
        if not UNLOCK_ALL_THEMES:
            for theme in THEMES:
                if before < theme["unlock_level"] <= after:
                    messages.append(f"New theme unlocked: {theme['name']}. Pick it in My Quests.")
    return messages


def award_task_completion(user_id, task):
    """Call right after a task is ticked as done. Returns messages to show the user."""
    conn = get_db_connection()
    try:
        ref = str(task["id"])
        if conn.execute("SELECT 1 FROM xp_events WHERE user_id = ? AND kind = 'task' AND ref = ?", (user_id, ref)).fetchone():
            return []                       # this task already paid out once

        before = _total(conn, user_id)
        day_iso = _today().isoformat()
        base = PRIORITY_XP.get(task["priority"], 10)
        used = _task_xp_today(conn, user_id, day_iso)
        award = max(0, min(base, DAILY_TASK_XP_CAP - used))

        try:
            deadline = datetime.strptime(f"{task['deadline_date']} {task['deadline_time']}", "%Y-%m-%d %H:%M")
            on_time = 1 if _now() <= deadline else 0
        except (ValueError, TypeError):
            on_time = 0

        conn.execute(
            """INSERT OR IGNORE INTO xp_events (user_id, kind, ref, xp, day, priority, category, on_time)
               VALUES (?, 'task', ?, ?, ?, ?, ?, ?)""",
            (user_id, ref, award, day_iso, task["priority"], task["category"], on_time),
        )

        if award == base:
            messages = [f"Task completed! +{award} XP"]
        elif award > 0:
            messages = [f"Task completed! +{award} XP (daily XP cap reached)"]
        else:
            messages = ["Task completed. You've reached today's XP cap, so no XP this time."]

        messages += _claim_new_quests(conn, user_id)
        conn.commit()
        messages += _level_messages(before, _total(conn, user_id))
        return messages
    finally:
        conn.close()


def sync_quests(user_id):
    """Check today's quests (e.g. 'add a task') and pay out finished ones. Returns messages."""
    conn = get_db_connection()
    try:
        before = _total(conn, user_id)
        messages = _claim_new_quests(conn, user_id)
        conn.commit()
        return messages + _level_messages(before, _total(conn, user_id))
    finally:
        conn.close()


def get_progress(user_id):
    """Everything the pages need to show XP, level, streak and today's quests."""
    conn = get_db_connection()
    try:
        info = level_info(_total(conn, user_id))
        today = _today()
        day_iso = today.isoformat()
        claimed = _claimed_slots(conn, user_id, day_iso)

        quests = []
        for q in quests_for(today):
            progress = min(_progress(conn, user_id, day_iso, q), q["goal"])
            quests.append({**q, "progress": progress, "pct": round(progress / q["goal"] * 100), "done": q["slot"] in claimed})

        current, best = _streaks(conn, user_id)
        quests_claimed_total = conn.execute(
            "SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND kind = 'quest'", (user_id,)
        ).fetchone()[0]

        return {
            **info,
            "quests": quests,
            "quests_done": sum(1 for q in quests if q["done"]),
            "quests_total": len(quests),
            "quest_xp": QUEST_XP,
            "streak": current,
            "best_streak": best,
            "quests_claimed_total": quests_claimed_total,
            "task_xp_today": _task_xp_today(conn, user_id, day_iso),
            "daily_cap": DAILY_TASK_XP_CAP,
        }
    finally:
        conn.close()


# ---------- Themes ----------

def _is_unlocked(theme, level):
    return UNLOCK_ALL_THEMES or level >= theme["unlock_level"]


def get_user_theme(user_id):
    """The user's chosen theme key, or the default if it's missing or still locked."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT value FROM user_prefs WHERE user_id = ? AND key = 'theme'", (user_id,)
        ).fetchone()
        if row and row["value"] in THEMES_BY_KEY:
            level = level_info(_total(conn, user_id))["level"]
            if _is_unlocked(THEMES_BY_KEY[row["value"]], level):
                return row["value"]
        return DEFAULT_THEME
    finally:
        conn.close()


def set_user_theme(user_id, key):
    """Returns (ok, message)."""
    theme = THEMES_BY_KEY.get(key)
    if theme is None:
        return False, "That theme doesn't exist."
    conn = get_db_connection()
    try:
        level = level_info(_total(conn, user_id))["level"]
        if not _is_unlocked(theme, level):
            return False, f"{theme['name']} is still locked. Reach level {theme['unlock_level']} to unlock it."
        conn.execute(
            "INSERT INTO user_prefs (user_id, key, value) VALUES (?, 'theme', ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user_id, key),
        )
        conn.commit()
        return True, f"Theme changed to {theme['name']}."
    finally:
        conn.close()


def list_themes(level, current_key):
    return [
        {
            "key": t["key"],
            "name": t["name"],
            "unlock_level": t["unlock_level"],
            "unlocked": _is_unlocked(t, level),
            "active": t["key"] == current_key,
            "swatches": [t["vars"]["primary"], t["vars"].get("bg", "#f5f6fa"), t["vars"].get("panel", "#ffffff"), t["vars"].get("text", "#1f2430")],
        }
        for t in THEMES
    ]


def next_theme_unlock(level):
    """The next locked theme, or None when everything is unlocked."""
    if UNLOCK_ALL_THEMES:
        return None
    for t in THEMES:
        if level < t["unlock_level"]:
            return t
    return None


def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def theme_css(key):
    """CSS that sets the theme's variables. Empty for the default theme."""
    theme = THEMES_BY_KEY.get(key)
    if theme is None or key == DEFAULT_THEME:
        return ""
    values = dict(theme["vars"])
    values["primary-soft"] = _hex_to_rgba(values["primary"], 0.14 if theme.get("dark") else 0.1)
    body = "".join(f"--{name}: {value};" for name, value in values.items())
    if theme.get("dark"):
        body += "color-scheme: dark;"
    return f":root{{{body}}}"