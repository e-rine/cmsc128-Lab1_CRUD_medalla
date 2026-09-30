import os
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

from backend.database import (
    DB_PATH,
    init_db,
    get_all_tasks,
    get_task_by_id,
    create_task,
    update_task,
    delete_task,
    toggle_task_complete,
    create_user,
    get_user_by_email,
)

app = Flask(__name__, template_folder="webpages")
app.secret_key = "dev-secret-key-change-this-later"

# Create/upgrade the tables whenever the app loads (python app.py, flask run, ...)
init_db()
print("Using database file:", os.path.abspath(DB_PATH))


# ---------- Template filters ----------

@app.template_filter("format_deadline")
def format_deadline(task):
    """'2026-09-10' + '15:30' -> 'Sep 10, 2026 · 3:30 PM'
    (built without %-d/%-I since those strftime flags don't work on Windows)"""
    dt = datetime.strptime(f"{task['deadline_date']} {task['deadline_time']}", "%Y-%m-%d %H:%M")
    hour_12 = dt.hour % 12 or 12
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} \u00b7 {hour_12}:{dt.strftime('%M')} {dt.strftime('%p')}"


@app.template_filter("is_overdue")
def is_overdue(task):
    dt = datetime.strptime(f"{task['deadline_date']} {task['deadline_time']}", "%Y-%m-%d %H:%M")
    return dt < datetime.now() and not task["is_completed"]


# ---------- Helper ----------

def redirect_back():
    return redirect(request.referrer or url_for("my_tasks"))


def login_required(view):
    """Send people to /login if they aren't logged in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.method == "DELETE":      # called by fetch() from the undo toast
                return "", 401
            flash("Please log in first.", "error")
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)
    return wrapped


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/homepage")
def homepage():
    return render_template("homepage.html")


@app.route("/login-signup", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("my_tasks"))
        return render_template("login_signup.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Incorrect email or password.", "error")
        return redirect(url_for("login_page"))

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("my_tasks"))


@app.route("/signup", methods=["POST"])
def signup():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")

    if not name or not email or len(password) < 8 or password != confirm:
        flash("Please fill in all fields correctly (password must be at least 8 characters).", "error")
        return redirect(url_for("login_page") + "#signup")

    if not create_user(name, email, generate_password_hash(password)):
        flash("That email is already registered.", "error")
        return redirect(url_for("login_page") + "#signup")

    flash("Account created. You can log in now.", "success")
    return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/my-tasks")
@login_required
def my_tasks():
    sort_by = request.args.get("sort", "due_date")
    tag = request.args.get("tag", "")
    priority = request.args.get("priority", "")

    tasks = get_all_tasks(session["user_id"], sort_by=sort_by, tag=tag or None, priority=priority or None)
    return render_template(
        "my_tasks.html",
        tasks=tasks,
        sort_by=sort_by,
        selected_tag=tag,
        selected_priority=priority,
    )


@app.route("/add-task", methods=["POST"])
@login_required
def add_task():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline_date = request.form.get("deadline_date", "")
    deadline_time = request.form.get("deadline_time", "")
    priority = request.form.get("priority", "medium")
    category = request.form.get("category", "other")

    if not title or not deadline_date or not deadline_time:
        flash("Title, deadline date, and deadline time are required.", "error")
        return redirect_back()

    create_task(session["user_id"], title, description, deadline_date, deadline_time, priority, category)
    flash("Task added successfully.", "success")
    return redirect_back()


@app.route("/edit-task/<int:task_id>", methods=["POST"])
@login_required
def edit_task(task_id):
    if get_task_by_id(task_id, session["user_id"]) is None:
        flash("That task no longer exists.", "error")
        return redirect_back()

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    deadline_date = request.form.get("deadline_date", "")
    deadline_time = request.form.get("deadline_time", "")
    priority = request.form.get("priority", "medium")
    category = request.form.get("category", "other")

    if not title or not deadline_date or not deadline_time:
        flash("Title, deadline date, and deadline time are required.", "error")
        return redirect_back()

    update_task(task_id, session["user_id"], title, description, deadline_date, deadline_time, priority, category)
    flash("Task updated.", "success")
    return redirect_back()


@app.route("/delete-task/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task_route(task_id):
    if get_task_by_id(task_id, session["user_id"]) is None:
        flash("That task no longer exists.", "error")
        return redirect_back()

    delete_task(task_id, session["user_id"])
    return redirect_back()


@app.route("/toggle-task/<int:task_id>", methods=["POST"])
@login_required
def toggle_task(task_id):
    if get_task_by_id(task_id, session["user_id"]) is None:
        flash("That task no longer exists.", "error")
        return redirect_back()

    toggle_task_complete(task_id, session["user_id"])
    return redirect_back()


if __name__ == "__main__":
    app.run(debug=True)