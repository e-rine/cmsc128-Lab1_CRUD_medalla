import os
import re
import sqlite3
import time


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL.startswith("postgres://"):         
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "todolist.db")

APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "").strip()
if APP_TIMEZONE:
    os.environ["TZ"] = APP_TIMEZONE
    if hasattr(time, "tzset"):
        time.tzset()

if USE_POSTGRES:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    IntegrityError = psycopg2.IntegrityError
else:
    IntegrityError = sqlite3.IntegrityError


# ---------- Postgres adapter ----------
# Makes a Postgres connection behave like the sqlite3 one the rest of the code expects:
# conn.execute(sql, params), "?" placeholders, rows readable by name AND by position.

def _to_pg(sql):
    """Translate the few SQLite-only bits of our SQL into Postgres."""
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = sql.replace("datetime('now', 'localtime')", "to_char(now(), 'YYYY-MM-DD HH24:MI:SS')")
    if re.match(r"\s*INSERT OR IGNORE INTO", sql, re.I):
        sql = re.sub(r"INSERT OR IGNORE INTO", "INSERT INTO", sql, count=1, flags=re.I)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return sql.replace("?", "%s")


class _Row(tuple):
    def __new__(cls, values, names):
        row = super().__new__(cls, values)
        row._names = names
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return tuple.__getitem__(self, self._names.index(key))
            except ValueError:
                raise KeyError(key)
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._names)


class _Cursor:
    def __init__(self, cur):
        self._cur = cur

    @property
    def rowcount(self):
        return self._cur.rowcount

    def _wrap(self, row):
        return _Row(row, [d[0] for d in self._cur.description])

    def fetchone(self):
        row = self._cur.fetchone()
        return None if row is None else self._wrap(row)

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


_pool = None
_last_used = {}         
_CHECK_AFTER_SECONDS = 20


class _PgConnection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        cur = self._raw.cursor()
        cur.execute(_to_pg(sql), tuple(params) if params else None)
        return _Cursor(cur)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        if self._raw is None:
            return
        raw, self._raw = self._raw, None
        broken = False
        try:
            raw.rollback()               # drop any unfinished transaction before reusing the connection
        except Exception:
            broken = True
        if broken:
            _last_used.pop(id(raw), None)
        else:
            _last_used[id(raw)] = time.monotonic()
        _pool.putconn(raw, close=broken)


def _pg_connect():
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            1, 5, dsn=DATABASE_URL, connect_timeout=15,
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        )
    last_error = None
    for _ in range(3):
        raw = _pool.getconn()
        try:
            seen = _last_used.get(id(raw))
            if seen is None or time.monotonic() - seen > _CHECK_AFTER_SECONDS:
                cur = raw.cursor()
                if APP_TIMEZONE:
                    cur.execute("SELECT set_config('TimeZone', %s, false)", (APP_TIMEZONE,))
                else:
                    cur.execute("SELECT 1")
                raw.commit()
            return _PgConnection(raw)
        except Exception as error:
            last_error = error
            _last_used.pop(id(raw), None)
            _pool.putconn(raw, close=True)
    raise last_error


def get_db_connection():
    if USE_POSTGRES:
        return _pg_connect()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table):
    if USE_POSTGRES:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? AND table_schema = current_schema()", (table,)
        ).fetchall()
        return [r[0] for r in rows]
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def table_exists(conn, table):
    if USE_POSTGRES:
        return conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ? AND table_schema = current_schema()",
            (table,),
        ).fetchone() is not None
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            list_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            deadline_date TEXT NOT NULL,
            deadline_time TEXT NOT NULL,
            priority TEXT NOT NULL,
            category TEXT NOT NULL,
            is_completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    columns = table_columns(conn, "tasks")
    if "user_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")
    if "list_id" not in columns:
        # NULL = personal task (visible only to tasks.user_id)
        # A number = task in that collaborative list
        conn.execute("ALTER TABLE tasks ADD COLUMN list_id INTEGER")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # Collaborative lists 
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # Who can see a list. The owner is always inserted here too.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS list_members (
            list_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            added_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (list_id, user_id)
        )
    """)

    conn.commit()
    conn.close()


# ---------- Tasks ----------
# A user can access a task if either:
#   - it's personal (list_id IS NULL) 
#   - it belongs to a list they are a member of.
ACCESS_CLAUSE = """(
    (tasks.list_id IS NULL AND tasks.user_id = ?)
    OR tasks.list_id IN (SELECT list_id FROM list_members WHERE user_id = ?)
)"""


def get_all_tasks(user_id, sort_by="due_date", tag=None, priority=None, list_id=None):
    conn = get_db_connection()
    query = """SELECT tasks.*, users.name AS creator_name
               FROM tasks LEFT JOIN users ON users.id = tasks.user_id"""

    if list_id is None:
        conditions = ["tasks.list_id IS NULL", "tasks.user_id = ?"]
        params = [user_id]
    else:
        conditions = ["tasks.list_id = ?"]
        params = [list_id]

    if tag:
        conditions.append("tasks.category = ?")
        params.append(tag)
    if priority:
        conditions.append("tasks.priority = ?")
        params.append(priority)

    query += " WHERE " + " AND ".join(conditions)

    # sort the results based on what was picked in the dropdown
    if sort_by == "date_added":
        order_clause = "tasks.created_at DESC"
    elif sort_by == "priority":
        order_clause = "CASE tasks.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END ASC, tasks.deadline_date ASC"
    elif sort_by == "tag":
        order_clause = "tasks.category ASC, tasks.deadline_date ASC"
    else:
        order_clause = "tasks.deadline_date ASC, tasks.deadline_time ASC"

    query += f" ORDER BY {order_clause}"

    tasks = conn.execute(query, params).fetchall()
    conn.close()
    return tasks


def get_task_by_id(task_id, user_id):
    conn = get_db_connection()
    task = conn.execute(
        f"SELECT * FROM tasks WHERE tasks.id = ? AND {ACCESS_CLAUSE}",
        (task_id, user_id, user_id),
    ).fetchone()
    conn.close()
    return task


def create_task(user_id, title, description, deadline_date, deadline_time, priority, category, list_id=None):
    """list_id=None creates a personal task. The caller must check list membership first."""
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO tasks (user_id, list_id, title, description, deadline_date, deadline_time, priority, category)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, list_id, title, description, deadline_date, deadline_time, priority, category),
    )
    conn.commit()
    conn.close()


def update_task(task_id, user_id, title, description, deadline_date, deadline_time, priority, category):
    conn = get_db_connection()
    conn.execute(
        f"""UPDATE tasks
           SET title = ?, description = ?, deadline_date = ?, deadline_time = ?, priority = ?, category = ?
           WHERE tasks.id = ? AND {ACCESS_CLAUSE}""",
        (title, description, deadline_date, deadline_time, priority, category, task_id, user_id, user_id),
    )
    conn.commit()
    conn.close()


def toggle_task_complete(task_id, user_id):
    conn = get_db_connection()
    conn.execute(
        f"UPDATE tasks SET is_completed = 1 - is_completed WHERE tasks.id = ? AND {ACCESS_CLAUSE}",
        (task_id, user_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_task(task_id, user_id):
    conn = get_db_connection()
    conn.execute(
        f"DELETE FROM tasks WHERE tasks.id = ? AND {ACCESS_CLAUSE}",
        (task_id, user_id, user_id),
    )
    conn.commit()
    conn.close()


# ---------- Users ----------

def create_user(name, email, password_hash):
    """Returns True if the user was created, False if the email is already taken."""
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return True
    except IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def update_user_name(user_id, name):
    conn = get_db_connection()
    conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
    conn.commit()
    conn.close()


def update_user_email(user_id, email):
    """Returns True if updated, False if another account already uses that email."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        conn.commit()
        return True
    except IntegrityError:
        return False
    finally:
        conn.close()


def update_user_password(user_id, password_hash):
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


# ---------- Password reset tokens ----------
# Only a SHA-256 hash of the token is stored

def create_reset_token(user_id, token_hash, expires_at):
    """Stores a new reset token. Any earlier tokens for this user stop working."""
    conn = get_db_connection()
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    conn.execute(
        "INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, token_hash, expires_at),
    )
    conn.commit()
    conn.close()


def get_reset_by_hash(token_hash):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT * FROM password_resets WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    conn.close()
    return row


def delete_reset_tokens(user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM password_resets WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()



# ---------- Collaborative lists ----------

def create_list(owner_id, name):
    # Creates a list and adds the owner as its first member. Returns the new list id
    conn = get_db_connection()
    try:
        if USE_POSTGRES:
            list_id = conn.execute(
                "INSERT INTO lists (name, owner_id) VALUES (?, ?) RETURNING id", (name, owner_id)
            ).fetchone()[0]
        else:
            list_id = conn.execute(
                "INSERT INTO lists (name, owner_id) VALUES (?, ?)", (name, owner_id)
            ).lastrowid
        conn.execute(
            "INSERT INTO list_members (list_id, user_id) VALUES (?, ?)", (list_id, owner_id)
        )
        conn.commit()
        return list_id
    finally:
        conn.close()


def get_lists_for_user(user_id):
    # Every list the user belongs to 
    conn = get_db_connection()
    lists = conn.execute(
        """SELECT lists.*,
                  owner.name AS owner_name,
                  (SELECT COUNT(*) FROM list_members lm2 WHERE lm2.list_id = lists.id) AS member_count
           FROM lists
           JOIN list_members ON list_members.list_id = lists.id
           JOIN users AS owner ON owner.id = lists.owner_id
           WHERE list_members.user_id = ?
           ORDER BY LOWER(lists.name) ASC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return lists


def get_list_for_user(list_id, user_id):
    # Returns the list only if the user is a member, else None
    conn = get_db_connection()
    row = conn.execute(
        """SELECT lists.* FROM lists
           JOIN list_members ON list_members.list_id = lists.id
           WHERE lists.id = ? AND list_members.user_id = ?""",
        (list_id, user_id),
    ).fetchone()
    conn.close()
    return row


def is_list_owner(list_id, user_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT 1 FROM lists WHERE id = ? AND owner_id = ?", (list_id, user_id)
    ).fetchone()
    conn.close()
    return row is not None


def add_member(list_id, user_id):
    # Returns True if added, False if already a member.
    # Doesn't check ownership, so the route must call is_list_owner() first
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO list_members (list_id, user_id) VALUES (?, ?)", (list_id, user_id)
        )
        conn.commit()
        return True
    except IntegrityError:
        return False
    finally:
        conn.close()


def get_members(list_id):
    # Members of a list, owner first 
    conn = get_db_connection()
    members = conn.execute(
        """SELECT users.id, users.name, users.email,
                  (users.id = lists.owner_id) AS is_owner
           FROM list_members
           JOIN users ON users.id = list_members.user_id
           JOIN lists ON lists.id = list_members.list_id
           WHERE list_members.list_id = ?
           ORDER BY is_owner DESC, LOWER(users.name) ASC""",
        (list_id,),
    ).fetchall()
    conn.close()
    return members

def rename_list(list_id, name):
    # Doesn't check ownership, so the route must call is_list_owner() first
    conn = get_db_connection()
    try:
        conn.execute("UPDATE lists SET name = ? WHERE id = ?", (name, list_id))
        conn.commit()
    finally:
        conn.close()


def delete_list(list_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM tasks WHERE list_id = ?", (list_id,))
        conn.execute("DELETE FROM list_members WHERE list_id = ?", (list_id,))
        conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def remove_member(list_id, user_id):
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """DELETE FROM list_members
               WHERE list_id = ? AND user_id = ?
                 AND user_id != (SELECT owner_id FROM lists WHERE id = ?)""",
            (list_id, user_id, list_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()