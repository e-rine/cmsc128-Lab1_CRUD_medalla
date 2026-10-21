# SideQuest

SideQuest is a gamified to-do list web app that encourages users to complete quests and achievements by finishing their tasks. Each person has their own account, and every task belongs to the account that created it.

## Features

**Accounts and security**
- Sign up with a name, email, and password
- Log in and log out
- Password recovery by email (forgot password and reset password)
- Profile page to change the display name, email, and password
- Passwords are hashed, never stored as plain text

**Tasks**
- Add, edit, and delete tasks
- Mark tasks done or not done
- Each task has a title, description, deadline date and time, priority, and category (tag)
- Filter by tag and priority
- Sort by due date, date added, priority, or tag
- Overdue tasks are flagged
- Every query is limited to the logged-in user, so nobody can see or change another user's tasks

## Tech Stack

| Part | Choice |
|------|--------|
| Frontend | HTML, CSS, JavaScript (vanilla), rendered with Flask (Jinja) templates |
| Backend | Flask (Python) |
| Database | SQLite (`todolist.db`) |
| Authentication | Server-side sessions (Flask) with password hashing (Werkzeug) |
| Email | SMTP through Python's `smtplib` |

**Why this stack:** Flask is lightweight and pairs naturally with Python, so the whole project stays in one language. SQLite needs no separate server, account, or API keys. It is built into Python and stores everything in a single file, which is enough for a small project like this. Werkzeug comes installed with Flask, so password hashing needs no extra packages.

## Project Structure

```
todolist/
├── app.py                 # Flask app and all routes
├── backend/
│   ├── database.py        # All SQL queries (tasks, users, reset tokens)
│   └── mailer.py          # Sends the password reset email
├── webpages/              # HTML templates
├── todolist.db            # SQLite database (created automatically, not in Git)
├── .env                   # Private settings (not in Git)
└── .gitignore
```

## Running It Locally

**Requirements:** Python 3 installed.

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd todolist

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # Mac/Linux

# 3. Install dependencies
pip install flask

# 4. (Optional) Set up email, see "Email Setup" below

# 5. Run the app
python app.py
```

Then open **http://127.0.0.1:5000/** in your browser.

## Database Setup

No manual setup is needed. When the app starts, `init_db()` in `backend/database.py` creates `todolist.db` and its tables if they do not exist yet. It also upgrades older databases by adding the `user_id` column to `tasks`. Tasks created before accounts existed have no owner, so they will not show up for any user.

There is no seed data. Create an account on the sign up page to start.

**Tables**

| Table | Purpose | Main columns |
|-------|---------|--------------|
| `users` | Accounts | `id`, `name`, `email` (unique), `password_hash`, `created_at` |
| `tasks` | Tasks owned by a user | `id`, `user_id`, `title`, `description`, `deadline_date`, `deadline_time`, `priority`, `category`, `is_completed`, `created_at` |
| `password_resets` | Password reset tickets | `id`, `user_id`, `token_hash` (unique), `expires_at`, `created_at` |

## Email Setup

Password reset links are sent by email. Create a file named `.env` in the project root (next to `app.py`):

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=youremail@gmail.com
SMTP_PASSWORD=your-16-letter-app-password
SMTP_FROM=youremail@gmail.com
```

- For Gmail, use an **App Password**, not your normal password. You need 2-Step Verification turned on to create one.
- `SMTP_PORT` defaults to 587 and `SMTP_FROM` defaults to `SMTP_USER` if left out.
- `.env` is listed in `.gitignore` and must never be committed.

**Demo mode:** if `SMTP_HOST` is not set, or sending fails, no email is sent. The reset link is printed in the terminal instead, so the whole flow can still be tested. The terminal shows `Email ON` or `Email OFF` when the app starts.

## Routes

All data operations go through Flask routes in `app.py`, which read and write SQLite using functions in `backend/database.py`.

**Pages and accounts**

| Method | Route | What it does | Login required |
|--------|-------|--------------|----------------|
| GET | `/` | Landing page | No |
| GET | `/homepage` | Home page | Yes |
| GET, POST | `/login-signup` | Show the login/sign up page, and log in | No |
| POST | `/signup` | Create an account | No |
| GET | `/logout` | Clear the session and log out | No |
| GET | `/profile` | View profile | Yes |
| POST | `/profile/name` | Change display name | Yes |
| POST | `/profile/email` | Change email (needs current password) | Yes |
| POST | `/profile/password` | Change password (needs current password) | Yes |

**Password recovery**

| Method | Route | What it does | Login required |
|--------|-------|--------------|----------------|
| GET, POST | `/forgot-password` | Show the form, then create a reset ticket and email the link | No |
| GET, POST | `/reset-password/<token>` | Check the link, show the form, then save the new password | No |

**Tasks**

| Method | Route | Operation | What it does | Login required |
|--------|-------|-----------|--------------|----------------|
| GET | `/my-tasks` | Read | View your tasks (supports `sort`, `tag`, `priority` query values) | Yes |
| POST | `/add-task` | Create | Add a new task | Yes |
| POST | `/edit-task/<id>` | Update | Edit an existing task | Yes |
| POST | `/toggle-task/<id>` | Update | Mark a task done / not done | Yes |
| DELETE | `/delete-task/<id>` | Delete | Remove a task | Yes |

## How Authentication Works

**Sign up.** The form is sent to `/signup`. The app checks that all fields are filled, the password is at least 8 characters, and both password boxes match. The password is hashed with Werkzeug's `generate_password_hash` (a salted hash, scrypt by default) and `create_user()` inserts the account. The `email` column is `UNIQUE`, so a repeated email is rejected.

**Log in.** `/login-signup` looks the account up by email and checks the typed password against the saved hash with `check_password_hash`. If either the email or password is wrong, the same message is shown ("Incorrect email or password") so it does not reveal which one was wrong.

**Session.** After a successful login, the app stores `user_id` and `user_name` in the Flask session, which is a signed cookie kept in the browser. The `@login_required` decorator checks for `user_id` in the session before running a protected route. If it is missing, the person is redirected to the login page (or gets a `401` for the background delete request). Logging out calls `session.clear()`. Every page is sent with no-cache headers, so pressing Back after logout does not show a saved copy of a private page.

**Task ownership.** Every task query includes `WHERE user_id = ?` with the logged-in user's id, so users can only read, edit, toggle, or delete their own tasks.

## How Password Recovery Works

1. The person enters their email on `/forgot-password`.
2. If an account exists, the app creates a random token with `secrets.token_urlsafe(32)`.
3. Only the **SHA-256 hash** of the token is saved in `password_resets`, along with the user id and an expiry time 30 minutes away. The real token is never stored, so a leaked database cannot be used to open reset links. Any older ticket for that user is deleted first, so only the newest link works.
4. The app emails a link like `/reset-password/<token>` (or prints it in the terminal in demo mode).
5. The page always shows the same message ("Email has been sent"), whether or not the email has an account, so it cannot be used to find out who is registered.
6. When the link is opened, the app hashes the token from the URL and looks it up. If there is no match or it has expired, the person is sent back to request a new link.
7. On submit, the new password must be 8 to 128 characters, match the confirmation, and differ from the current password.
8. The new password is hashed and saved, the reset ticket is deleted (so the link works only once), the session is cleared, and the person is sent to log in.

Reset links last **30 minutes** (`RESET_TOKEN_MINUTES` in `app.py`).

## Notes

- The Flask `secret_key` in `app.py` is a development value. Change it before deploying anywhere public.
- `.env` and `todolist.db` should stay out of Git. Both are listed in `.gitignore`.