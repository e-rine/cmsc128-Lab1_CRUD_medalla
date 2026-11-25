# SideQuest

SideQuest is a gamified to-do list web app. Each person has their own account and private tasks, and people can also create groups to share a task list with others.

## Features

- Sign up, log in, log out, and reset a forgotten password by email
- Profile page to change your name, email, and password
- Add, edit, delete, and complete tasks (title, description, deadline, priority, tag)
- Filter by tag and priority, sort by due date, date added, priority, or tag
- Groups: create a group, add members by email, see members, remove members or leave, and delete the group
- Personal tasks are private, and group tasks are only visible to group members

## Tech Stack

| Part | Choice |
|------|--------|
| Frontend | HTML, CSS, vanilla JavaScript, Flask (Jinja) templates |
| Backend | Flask (Python) |
| Database | SQLite (`todolist.db`) |
| Login | Flask sessions, passwords hashed with Werkzeug |
| Email | SMTP (`smtplib`) |

## How Activity 1 and Activity 2 Were Merged

I did not merge two separate branches. I used `git switch` to create a new branch and move off the **act2** branch and built on top of it, so Activity 2's code already had unique user access and everything else was added as new commits on the same branch.


## Project Structure

```
todolist/
├── app.py              # Flask app and all routes
├── backend/
│   ├── database.py     # All SQL queries
│   └── mailer.py       # Sends the password reset email
├── webpages/           # HTML templates
├── static/             # CSS (styles/) and JavaScript (scripts/)
├── todolist.db         # SQLite database 
└── .env                # Email settings
```

## Installation and Running Locally

Requires Python 3 and Git.

```bash
# 1. Clone the repo and switch to the branch
git clone <your-repo-url>
cd todolist
git switch <branch-name>

# 2. Create and activate a virtual environment
python -m venv venv
venv\bin\Activate.ps1        # Windows PowerShell

# 3. Install dependencies
pip install flask

# 4. Run the app
python app.py
```

Open **http://127.0.0.1:5000/** and create an account. 

## Database Schema

| Table | Purpose | Main columns |
|-------|---------|--------------|
| `users` | Accounts | `id`, `name`, `email` (unique), `password_hash` |
| `tasks` | Personal or group tasks | `id`, `user_id`, `list_id`, `title`, `description`, `deadline_date`, `deadline_time`, `priority`, `category`, `is_completed` |
| `lists` | Groups | `id`, `name`, `owner_id` |
| `list_members` | Who is in which group | `list_id`, `user_id` |
| `password_resets` | Reset links (only a hash of the token is stored) | `id`, `user_id`, `token_hash`, `expires_at` |

**How they relate**

- A **user** creates **tasks** (`tasks.user_id`) and owns **lists** (`lists.owner_id`).
- A task with `list_id = NULL` is **personal**: only its creator can see it.
- A task with a `list_id` belongs to that **group**: every member can see and edit it.
- Users and lists are many-to-many through `list_members`. The owner is added there too when the group is created.
- The relationships are enforced in the code, not with SQLite `FOREIGN KEY` constraints.

## Ownership Checks

The server checks who is asking on every request. It always uses `session["user_id"]`, never an id sent from the browser.

**Tasks.** Every single-task query (get, edit, complete, delete) uses this rule in `backend/database.py`:

```python
ACCESS_CLAUSE = """(
    (tasks.list_id IS NULL AND tasks.user_id = ?)
    OR tasks.list_id IN (SELECT list_id FROM list_members WHERE user_id = ?)
)"""
```

A task is accessible only if it is your own personal task, or it is in a group you belong to.

**Groups.** Routes check membership first, then ownership:

```python
@app.route("/groups/<int:list_id>/delete", methods=["POST"])
@login_required
def delete_group(list_id):
    user_id = session["user_id"]
    if get_list_for_user(list_id, user_id) is None:   # not a member
        abort(404)
    if not is_list_owner(list_id, user_id):           # member, but not the owner
        return group_error("Only the owner can delete this group.")
    delete_list(list_id)
```

## Routes

| Method | Route | What it does | Check |
|--------|-------|--------------|-------|
| POST | `/signup` | Create an account | None |
| GET, POST | `/login-signup` | Log in | None |
| GET | `/logout` | Log out | None |
| GET, POST | `/forgot-password` | Request a reset link | None |
| GET, POST | `/reset-password/<token>` | Set a new password | Valid, unexpired token |
| GET | `/profile` | View profile | Logged in |
| POST | `/profile/name`, `/email`, `/password` | Update profile | Logged in (email and password also need the current password) |
| GET | `/my-tasks` | Your personal tasks | Only your personal tasks are returned |
| GET | `/my-tasks?list=<id>` | A group's tasks | Must be a member, else 404 |
| POST | `/add-task` | Add a task (to a group if `list_id` is sent) | Group: must be a member, else 404 |
| POST | `/edit-task/<id>` | Edit a task | `ACCESS_CLAUSE` |
| POST | `/toggle-task/<id>` | Mark done or not done | `ACCESS_CLAUSE` |
| DELETE | `/delete-task/<id>` | Delete a task | `ACCESS_CLAUSE` |
| GET | `/groups` | Your groups | Only groups you belong to |
| POST | `/groups/create` | Create a group | Logged in; you become the owner |
| POST | `/groups/<id>/members` | Add a member by email | Member (else 404), then owner |
| POST | `/groups/<id>/members/<member_id>/remove` | Remove a member, or leave | Member (else 404). Owner can remove anyone but themselves; others can only remove themselves. The owner can't be removed |
| POST | `/groups/<id>/delete` | Delete the group and its tasks | Member (else 404), then owner |

## Notes

- Password reset links last 30 minutes and only work once.
- `.env` and `todolist.db` are out of Git.