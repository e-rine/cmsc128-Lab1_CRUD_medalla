from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash

from backend.database import (
    init_db,
    get_all_tasks,
    get_task_by_id,
    create_task,
    update_task,
    delete_task,
    toggle_task_complete,
)

app = Flask(__name__, template_folder="webpages")
app.secret_key = "dev-secret-key-change-this-later"


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


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/my-tasks")
def my_tasks():
    sort_by = request.args.get("sort", "due_date")
    tag = request.args.get("tag", "")
    priority = request.args.get("priority", "")

    tasks = get_all_tasks(sort_by=sort_by, tag=tag or None, priority=priority or None)
    return render_template(
        "my_tasks.html",
        tasks=tasks,
        sort_by=sort_by,
        selected_tag=tag,
        selected_priority=priority,
    )


@app.route("/add-task", methods=["POST"])
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

    create_task(title, description, deadline_date, deadline_time, priority, category)
    flash("Task added successfully.", "success")
    return redirect_back()


@app.route("/edit-task/<int:task_id>", methods=["POST"])
def edit_task(task_id):
    if get_task_by_id(task_id) is None:
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

    update_task(task_id, title, description, deadline_date, deadline_time, priority, category)
    flash("Task updated.", "success")
    return redirect_back()


@app.route("/delete-task/<int:task_id>", methods=["POST"])
def delete_task_route(task_id):
    if get_task_by_id(task_id) is None:
        flash("That task no longer exists.", "error")
        return redirect_back()

    delete_task(task_id)
    flash("Task deleted successfully.", "success")
    return redirect_back()


@app.route("/toggle-task/<int:task_id>", methods=["POST"])
def toggle_task(task_id):
    if get_task_by_id(task_id) is None:
        flash("That task no longer exists.", "error")
        return redirect_back()

    toggle_task_complete(task_id)
    return redirect_back()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)