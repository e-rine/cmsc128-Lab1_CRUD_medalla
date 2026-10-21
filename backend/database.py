import sqlite3
import os


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "todolist.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

    # Older databases were created before tasks belonged to users / lists: add the columns.
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
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


# ---------- Tasks (every query is scoped to one user) ----------

def get_all_tasks(user_id, sort_by="due_date", tag=None, priority=None):
    conn = get_db_connection()
    query = "SELECT * FROM tasks"
    conditions = ["user_id = ?"]
    params = [user_id]

    if tag:
        conditions.append("category = ?")
        params.append(tag)
    if priority:
        conditions.append("priority = ?")
        params.append(priority)

    query += " WHERE " + " AND ".join(conditions)

    # Figure out how to sort the results based on what was picked in the dropdown
    if sort_by == "date_added":
        order_clause = "created_at DESC"
    elif sort_by == "priority":
        order_clause = "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END ASC, deadline_date ASC"
    elif sort_by == "tag":
        order_clause = "category ASC, deadline_date ASC"
    else:
        order_clause = "deadline_date ASC, deadline_time ASC"

    query += f" ORDER BY {order_clause}"

    tasks = conn.execute(query, params).fetchall()
    conn.close()
    return tasks


def get_task_by_id(task_id, user_id):
    conn = get_db_connection()
    task = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
    ).fetchone()
    conn.close()
    return task


def create_task(user_id, title, description, deadline_date, deadline_time, priority, category):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO tasks (user_id, title, description, deadline_date, deadline_time, priority, category)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, title, description, deadline_date, deadline_time, priority, category),
    )
    conn.commit()
    conn.close()


def update_task(task_id, user_id, title, description, deadline_date, deadline_time, priority, category):
    conn = get_db_connection()
    conn.execute(
        """UPDATE tasks
           SET title = ?, description = ?, deadline_date = ?, deadline_time = ?, priority = ?, category = ?
           WHERE id = ? AND user_id = ?""",
        (title, description, deadline_date, deadline_time, priority, category, task_id, user_id),
    )
    conn.commit()
    conn.close()


def toggle_task_complete(task_id, user_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE tasks SET is_completed = NOT is_completed WHERE id = ? AND user_id = ?",
        (task_id, user_id),
    )
    conn.commit()
    conn.close()


def delete_task(task_id, user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
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
    except sqlite3.IntegrityError:
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
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_user_password(user_id, password_hash):
    conn = get_db_connection()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


# ---------- Password reset tokens ----------
# Only a SHA-256 hash of the token is stored, so a leaked database
# can't be used to reset anyone's password.

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
        cursor = conn.execute(
            "INSERT INTO lists (name, owner_id) VALUES (?, ?)", (name, owner_id)
        )
        list_id = cursor.lastrowid
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
           ORDER BY lists.name COLLATE NOCASE ASC""",
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
    except sqlite3.IntegrityError:
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
           ORDER BY is_owner DESC, users.name COLLATE NOCASE ASC""",
        (list_id,),
    ).fetchall()
    conn.close()
    return members