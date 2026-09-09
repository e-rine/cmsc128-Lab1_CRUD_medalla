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
    conn.commit()
    conn.close()


# ---------- CRUD ----------

def get_all_tasks(sort_by="Due_date", tag=None, priority=None):
    conn = get_db_connection()
    query = "SELECT * FROM tasks"
    conditions = []
    params = []

    if tag:
        conditions.append("category = ?")
        params.append(tag)
    if priority:
        conditions.append("priority = ?")
        params.append(priority)

    if conditions:
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


def get_task_by_id(task_id):
    conn = get_db_connection()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return task


def create_task(title, description, deadline_date, deadline_time, priority, category):
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO tasks (title, description, deadline_date, deadline_time, priority, category)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (title, description, deadline_date, deadline_time, priority, category),
    )
    conn.commit()
    conn.close()


def update_task(task_id, title, description, deadline_date, deadline_time, priority, category):
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