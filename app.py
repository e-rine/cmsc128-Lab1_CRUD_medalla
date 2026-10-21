import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
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
    create_reset_token,
    get_reset_by_hash,
    delete_reset_tokens,
    create_list,
    get_lists_for_user,
    get_list_for_user,
    is_list_owner,
    add_member,
    get_members,
    delete_list,
    remove_member,
)
from backend.mailer import send_reset_email

app = Flask(__name__, template_folder="webpages")
# Set SECRET_KEY in your .env file; the fallback is only for local development.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-this-later")

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
@login_required
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


# ---------- Password recovery ----------

RESET_TOKEN_MINUTES = 30


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def get_valid_reset(token):
    """Returns the reset row if the token exists and hasn't expired, else None."""
    reset = get_reset_by_hash(hash_token(token))
    if reset is None:
        return None
    if datetime.now(timezone.utc) > datetime.fromisoformat(reset["expires_at"]):
        delete_reset_tokens(reset["user_id"])
        return None
    return reset


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    user = get_user_by_email(email) if email else None

    if user:
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_MINUTES)
        create_reset_token(user["id"], hash_token(token), expires.isoformat())
        link = url_for("reset_password", token=token, _external=True)
        send_reset_email(user["email"], user["name"], link, RESET_TOKEN_MINUTES)
    else:
        print(f"[password reset] requested for unknown email {email!r}; nothing sent.", flush=True)

    # Same answer whether or not the email exists, so this page can't be used
    # to find out who has an account.
    flash(
        f"Email has been sent."
        f"",
        "success",
    )
    return redirect(url_for("forgot_password"))


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    reset = get_valid_reset(token)
    if reset is None:
        flash("The link is invalid or has expired. Please request a new one.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "GET":
        return render_template("reset_password.html")

    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    user = get_user_by_id(reset["user_id"])

    error = None
    if user is None:
        error = "That account no longer exists."
    elif len(new_password) < 8:
        error = "Password must be at least 8 characters."
    elif len(new_password) > 128:
        error = "Password must be 128 characters or fewer."
    elif new_password != confirm_password:
        error = "Passwords don't match."
    elif check_password_hash(user["password_hash"], new_password):
        error = "Choose a password different from your current one."

    if error:
        flash(error, "error")
        return redirect(url_for("reset_password", token=token))

    update_user_password(user["id"], generate_password_hash(new_password))
    delete_reset_tokens(user["id"])       # the link works only once
    session.clear()
    flash("Password updated. Log in with your new password.", "success")
    return redirect(url_for("login_page"))


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
    return redirect(url_for("index"))

@app.route("/my-tasks")
@login_required
def my_tasks():
    sort_by = request.args.get("sort", "due_date")
    tag = request.args.get("tag", "")
    priority = request.args.get("priority", "")

    # ?list=ID shows that group's shared task list; no list = personal tasks
    list_id = request.args.get("list", type=int)
    current_list = None
    if list_id is not None:
        current_list = get_list_for_user(list_id, session["user_id"])
        if current_list is None:          # not a member -> pretend it doesn't exist
            abort(404)

    tasks = get_all_tasks(session["user_id"], sort_by=sort_by, tag=tag or None,
                          priority=priority or None, list_id=list_id)
    return render_template(
        "my_tasks.html",
        tasks=tasks,
        current_list=current_list,
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
        flash_section("error", "email", "Password is incorrect.")
    elif not EMAIL_PATTERN.match(email):
        flash_section("error", "email", "Please enter a valid email address.")
    elif email == user["email"]:
        flash_section("error", "email", "That's your current email address.")
    elif not update_user_email(user["id"], email):
        flash_section("error", "email", "That email is already in use.")
    else:
        flash_section("success", "email", "Email has been updated.")

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

    list_id = request.form.get("list_id", type=int)
    if list_id is not None and get_list_for_user(list_id, session["user_id"]) is None:
        abort(404)

    if not title or not deadline_date or not deadline_time:
        flash("Title, deadline date, and deadline time are required.", "error")
        return redirect_back()

    create_task(session["user_id"], title, description, deadline_date, deadline_time,
                priority, category, list_id=list_id)
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

@app.route("/groups")
@login_required
def groups():
    user_id = session["user_id"]
    groups = []
    for lst in get_lists_for_user(user_id):
        g = dict(lst)
        g["members"] = get_members(lst["id"])
        g["is_owner"] = lst["owner_id"] == user_id
        groups.append(g)
    return render_template("groups.html", groups=groups)


def wants_json():
    """True when the request came from the modals' fetch() call in groups.js."""
    return request.headers.get("X-Requested-With") == "fetch"


def group_error(message):
    """Report a validation error without closing the modal (JSON) or via flash (plain form)."""
    if wants_json():
        return jsonify(ok=False, error=message), 400
    flash(message, "error")
    return redirect(url_for("groups"))


def group_success(message):
    flash(message, "success")
    if wants_json():
        return jsonify(ok=True, redirect=url_for("groups"))
    return redirect(url_for("groups"))


@app.route("/groups/create", methods=["POST"])
@login_required
def create_group():
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()

    if not name:
        return group_error("Group name can't be empty.")
    if len(name) > 50:
        return group_error("Group name must be 50 characters or fewer.")

    members = []      # accounts to add, no duplicates
    invalid = []      # badly written emails, or emails with no account
    own_email = False
    seen = set()
    for raw in request.form.getlist("emails"):
        email = raw.strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)

        if not EMAIL_PATTERN.match(email):
            invalid.append(email)
            continue
        target = get_user_by_email(email)
        if target is None:
            invalid.append(email)
        elif target["id"] == user_id:
            own_email = True
        else:
            members.append(target)

    if own_email:
        return group_error("You can't add yourself. You're automatically the owner of the group.")
    if invalid:
        return group_error("Invalid or unregistered email: " + ", ".join(invalid))

    list_id = create_list(user_id, name)
    for target in members:
        add_member(list_id, target["id"])

    return group_success(f'Group "{name}" created.')


@app.route("/groups/<int:list_id>/members", methods=["POST"])
@login_required
def add_group_member(list_id):
    user_id = session["user_id"]

    # Not a member -> pretend it doesn't exist
    if get_list_for_user(list_id, user_id) is None:
        abort(404)
    if not is_list_owner(list_id, user_id):
        return group_error("Only the owner can add members.")

    email = request.form.get("email", "").strip().lower()
    target = get_user_by_email(email) if email else None

    if target is None:
        return group_error("No account found with that email.")
    if target["id"] == user_id:
        return group_error("You're already in this group.")
    if not add_member(list_id, target["id"]):
        return group_error(f"{target['name']} is already in this group.")
    return group_success(f"{target['name']} was added to the group.")


@app.route("/groups/<int:list_id>/delete", methods=["POST"])
@login_required
def delete_group(list_id):
    user_id = session["user_id"]

    # Not a member -> pretend it doesn't exist
    if get_list_for_user(list_id, user_id) is None:
        abort(404)
    if not is_list_owner(list_id, user_id):
        return group_error("Only the owner can delete this group.")

    name = get_list_for_user(list_id, user_id)["name"]
    delete_list(list_id)
    return group_success(f'Group "{name}" was deleted.')


@app.route("/groups/<int:list_id>/members/<int:member_id>/remove", methods=["POST"])
@login_required
def remove_group_member(list_id, member_id):
    user_id = session["user_id"]

    # Not a member -> pretend it doesn't exist
    if get_list_for_user(list_id, user_id) is None:
        abort(404)

    # The owner can remove anyone; other members can only remove themselves (leave).
    if not is_list_owner(list_id, user_id) and member_id != user_id:
        return group_error("Only the owner can remove other members.")

    if is_list_owner(list_id, member_id):
        return group_error("The owner can't be removed. Delete the group instead.")

    if not remove_member(list_id, member_id):
        return group_error("That person isn't in this group.")

    if member_id == user_id:
        return group_success("You left the group.")
    return group_success("Member removed.")


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(debug=True)