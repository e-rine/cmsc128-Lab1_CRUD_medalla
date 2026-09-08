import sqlite3
import os

# Database lives next to this file so the path works no matter where app.py is run from
DB_PATH = os.path.join(os.path.dirname(__file__), "todolist.db")


def get_db_connection():
    """Open a connection with row access by column name (like a dict)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the tasks table if it doesn't exist yet. Safe to call every startup."""
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            deadline_date TEXT NOT NULL,
            deadline_time TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'medium',
            category TEXT NOT NULL DEFAULT 'other',
            is_completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "priority" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium'")
    if "category" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN category TEXT NOT NULL DEFAULT 'other'")

    conn.commit()
    conn.close()


# ---------- CRUD ----------

SORT_COLUMNS = {
    "date_added": "created_at DESC",
    "due_date": "deadline_date ASC, deadline_time ASC",
    "priority": "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END ASC, deadline_date ASC",
    "tag": "category ASC, deadline_date ASC",
}


def get_all_tasks(sort_by="due_date", tag=None, priority=None):
    conn = get_db_connection()

    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if tag:
        query += " AND category = ?"
        params.append(tag)

    if priority:
        query += " AND priority = ?"
        params.append(priority)

    order_clause = SORT_COLUMNS.get(sort_by, SORT_COLUMNS["due_date"])
    query += f" ORDER BY {order_clause}"

    tasks = conn.execute(query, params).fetchall()
    conn.close()
    return tasks


def get_task_by_id(task_id):
    conn = get_db_connection()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return task


def create_task(title, description, deadline_date, deadline_time, priority="medium", category="other"):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO tasks (title, description, deadline_date, deadline_time, priority, category)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, deadline_date, deadline_time, priority, category),
    )
    conn.commit()
    conn.close()


def update_task(task_id, title, description, deadline_date, deadline_time, priority="medium", category="other"):
    conn = get_db_connection()
    conn.execute(
        """UPDATE tasks
           SET title = ?, description = ?, deadline_date = ?, deadline_time = ?, priority = ?, category = ?
           WHERE id = ?""",
        (title, description, deadline_date, deadline_time, priority, category, task_id),
    )
    conn.commit()
    conn.close()


def toggle_task_complete(task_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE tasks SET is_completed = NOT is_completed WHERE id = ?", (task_id,)
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()