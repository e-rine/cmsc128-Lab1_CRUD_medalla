import os
import re
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
    get_user_by_id,
    update_user_name,
    update_user_email,
    update_user_password,
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


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def flash_section(kind, section, message):
    """Flash a message that shows up inside one card of the profile page."""
    flash(message, f"{kind}-{section}")


def back_to_profile(section):
    return redirect(url_for("profile") + f"#{section}-section")


@app.route("/profile")
@login_required
def profile():
    user = get_user_by_id(session["user_id"])
    if user is None:                      # account no longer exists
        session.clear()
        return redirect(url_for("login_page"))

    joined = datetime.strptime(user["created_at"], "%Y-%m-%d %H:%M:%S")
    member_since = f"{joined.strftime('%B')} {joined.day}, {joined.year}"
    return render_template("profile.html", user=user, member_since=member_since)


@app.route("/profile/name", methods=["POST"])
@login_required
def update_name():
    name = request.form.get("name", "").strip()

    if not name:
        flash_section("error", "name", "Display name can't be empty.")
        return back_to_profile("name")
    if len(name) > 50:
        flash_section("error", "name", "Display name must be 50 characters or fewer.")
        return back_to_profile("name")

    update_user_name(session["user_id"], name)
    session["user_name"] = name           # so the sidebar updates right away
    flash_section("success", "name", "Display name updated.")
    return back_to_profile("name")


@app.route("/profile/email", methods=["POST"])
@login_required
def update_email():
    user = get_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login_page"))

    email = request.form.get("email", "").strip().lower()
    current_password = request.form.get("current_password", "")

    if not check_password_hash(user["password_hash"], current_password):
        flash_section("error", "email", "Current password is incorrect.")
    elif not EMAIL_PATTERN.match(email):
        flash_section("error", "email", "Please enter a valid email address.")
    elif email == user["email"]:
        flash_section("error", "email", "That's already your email address.")
    elif not update_user_email(user["id"], email):
        flash_section("error", "email", "That email is already used by another account.")
    else:
        flash_section("success", "email", "Email updated. Use it the next time you log in.")

    return back_to_profile("email")


@app.route("/profile/password", methods=["POST"])
@login_required
def update_password():
    user = get_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login_page"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(user["password_hash"], current_password):
        flash_section("error", "password", "Current password is incorrect.")
    elif len(new_password) < 8:
        flash_section("error", "password", "New password must be at least 8 characters.")
    elif len(new_password) > 128:
        flash_section("error", "password", "New password must be 128 characters or fewer.")
    elif new_password != confirm_password:
        flash_section("error", "password", "New passwords don't match.")
    elif check_password_hash(user["password_hash"], new_password):
        flash_section("error", "password", "New password must be different from your current one.")
    else:
        update_user_password(user["id"], generate_password_hash(new_password))
        flash_section("success", "password", "Password changed.")

    return back_to_profile("password")


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