# SideQuest

SideQuest is a gamified to-do list web app. Each person has their own account and private tasks, and people can also create groups to share a task list with others. Finishing tasks earns XP, levels, daily quests, streaks and color themes.

**Live app:** https://sidequest-ilz2.onrender.com 

## Features

**Accounts**
- Sign up, log in, log out, and reset a forgotten password by email
- Show/hide toggle on password fields
- Profile page to change your name, email, and password
- Landing and onboarding page for new visitors

**Tasks**
- Add, edit, delete, and complete tasks (title, description, deadline, priority, category)
- Filter by category and priority, sort by due date, date added, priority, or category
- Click a task to open a **details window** with the full description, deadline, priority and category, and edit the task in the same window
- Long titles and descriptions are shortened to one line with "..." in the list; the details window shows everything
- Deadline date and time are shown in separate columns
- **Hide completed tasks** checkbox; the choice is saved per account and also applies to the floating window
- Deleting a task shows an **Undo** pop-up for 5 seconds before it is really deleted
- Messages (task completed, task updated, errors) appear as small **pop-ups** at the bottom of the screen and fade away on their own

**Homepage**
- Greeting, level and XP bar, streak, and stats (total, completed, pending, overdue)
- "Due soon" list (the 3 tasks due next), quick add form, today's daily quests, and completion rate
- Uses the full width of the window and adapts when the window is resized

**Gamification**
- **XP and levels:** finishing a task gives 10 / 20 / 30 XP for low / medium / high priority. Every 100 XP is one level.
- **Daily XP cap:** task XP is capped at 100 per day, and each task pays out only once, so splitting a task or un-ticking and re-ticking it does not farm XP.
- **My Quests page:** 3 daily quests per day, picked by rotating through 7 quest types (finish any, medium, high or low priority tasks, add tasks, finish before the deadline, tasks from different categories). Each quest gives 10 XP.
- **Streak:** the streak goes up by one for every day on which all 3 daily quests are done, and resets after a missed day. The best streak is remembered.
- **Color themes (unlocked by level):** Indigo (level 1), Ocean (5), Forest (10), Sunset (15), Rose (20) and Midnight, a dark theme (25). Pick one on the My Quests page. 
- **Achievements:** badges such as First Quest, Task Master, High Roller, Clean Slate, Team Player, Quest Starter, On Fire and Week Warrior, shown on the My Quests page.

**Floating task window**
- "Pop out tasks" in the sidebar opens a small always-on-top window (Chrome or Edge 116+) that stays visible while you use other tabs and apps
- It shows your level, streak and quests, lists your tasks, lets you add a task, and lets you tick them off (with a short buffer so a misclick is easy to undo)
- It follows the same "Hide completed" setting and your color theme
- The window stays open as long as the SideQuest tab stays open

**Groups**
- Manage everything from one modal: create a group (and invite members by email), rename it, add members, remove members or leave, and delete the group
- Personal tasks are private, and group tasks are only visible to group members

## Notes

- Password reset links last 30 minutes and only work once.
- `.env` and `todolist.db` are out of Git, so never commit your database URL, email keys or `SECRET_KEY`.
- The floating window needs Chrome or Edge 116+ and a secure address (HTTPS, or `localhost` while developing).
- Completed tasks keep the XP they earned even if they are un-ticked or deleted later.
- Pages are sent with no-cache headers so a newly picked theme and task changes show up right away.

## Backend, Database and What Was Refactored

**Backend:** Python with the Flask framework (Jinja templates for pages, plus JSON routes for the floating window and the group modals).

**Database:** PostgreSQL in production, SQLite for quick local use. The app picks one at startup:

- If the `DATABASE_URL` environment variable starts with `postgresql://` (or `postgres://`), it connects to PostgreSQL through `psycopg2`.
- If it is not set, it falls back to a local SQLite file (`todolist.db`), so a fresh clone runs with no database setup.

### What I refactored and why

| Area | What changed | Why |
|------|--------------|-----|
| Database | Added PostgreSQL support and deployment setup. A small adapter in `backend/database.py` translates the SQLite-style SQL (`?` placeholders, `AUTOINCREMENT`, `INSERT OR IGNORE`, `datetime('now')`) into Postgres, so all queries are written once and run on both. | SQLite is a local file and is not a good fit for a hosted server. Postgres is a real database server the deployed app can connect to, and keeping SQLite working means anyone can still run the project locally without installing anything. |
| Database round trips | Postgres connections come from a connection pool with TCP keep-alives, and a connection is only health-checked after 20 seconds idle. Settings such as the theme and "Hide completed" are stored in one `user_prefs` table, and the old `user_settings` table is migrated into it once and dropped. | Opening a new connection to a remote database on every query is slow. Reusing connections and skipping the check on busy connections means fewer round trips and faster pages. |
| Mailer | `backend/mailer.py` now tries a Google Apps Script (Gmail), then Brevo, then plain SMTP, and finally prints the reset link in the terminal. Email is sent over HTTPS where possible. | Free hosting tiers such as Render often block SMTP ports. HTTPS-based sending works there, and the fallback chain means password reset never breaks the flow. |
| Routing | Signup and login redirects were cleaned up. Errors re-render the page with the name and email kept, and a new account is logged in right away. | Less duplicated route logic and a smoother signup experience. |
| UI / frontend | Reorganized the CSS into a shared base plus one stylesheet per page, made the panels fill the full window width, and replaced inline messages with toast pop-ups. Task details and editing now open in a modal, group management (create, rename, members, leave, delete) is in one modal, and I added a landing and onboarding page, a tweaked logo and a show/hide eye on password fields. | Easier to maintain and no more style modal between pages. The layout adapts to any window size, messages no longer shift the page, and tasks and groups can be managed without leaving the page. |
| Gamification | Added quests, streaks, achievements, and levels. Themes also unlock by level. | Gives players something to work toward. |
| Code quality | Added and edited comments on functions. | Easier for others to read and maintain. |

## Tech Stack

| Part | Choice |
|------|--------|
| Frontend | HTML, CSS, vanilla JavaScript, Flask (Jinja) templates |
| Backend | Flask (Python) |
| Database | PostgreSQL via `psycopg2` (production); SQLite (local fallback) |
| Email | Google Apps Script (Gmail), Brevo API, or SMTP (`smtplib`), whichever is configured |
| Hosting | <!-- TODO: confirm, e.g. Render (web service + Postgres) --> |
| Floating window | Document Picture-in-Picture API (browser feature, no library) |

## Installation and Running Locally

Requires Python 3 and Git. PostgreSQL is optional: without `DATABASE_URL` the app uses a local SQLite file.

```bash
# 1. Clone the repo (the main branch has the final version)
git clone <your-repo-url>
cd todolist

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # macOS / Linux

# 3. Install dependencies
pip install flask psycopg2-binary
# TODO: if you have a requirements.txt, use: pip install -r requirements.txt

# 4. (Optional) Use PostgreSQL instead of SQLite
#    Create a database, then put its URL in .env (see Configuration)

# 5. Run the app
python app.py
```

Open **http://127.0.0.1:5000/** and create an account. The tables are created automatically the first time the app starts, and the terminal prints which database is in use. Without an email service configured, password reset links are printed in the terminal.

## Configuration

Settings are read from environment variables, which can also be put in a `.env` file in the project root (it is not in Git). Real environment variables win over `.env`.

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Signs the login cookie. Set a long random value (`python -c "import secrets; print(secrets.token_hex(32))"`). If missing, an insecure development key is used. |
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql://user:password@localhost:5432/sidequest`. If empty, SQLite (`todolist.db`) is used. |
| `APP_TIMEZONE` | Optional time zone for dates and deadlines, e.g. `Asia/Manila`. |
| `APPS_SCRIPT_URL`, `APPS_SCRIPT_SECRET` | Send reset emails through a Google Apps Script web app that uses your Gmail (HTTPS). Tried first. |
| `BREVO_API_KEY`, `MAIL_FROM` | Send reset emails through Brevo's HTTPS API. Tried second. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Send through a normal SMTP server. Tried third. |

If none of the email settings are set (or sending fails), the app runs in demo mode: the reset link is printed in the terminal instead of emailed.

## Accessing the Deployed App

**Live URL:** https://sidequest-ilz2.onrender.com

- Open the link in any modern browser. No installation or special setup is needed on the instructor's end.
- Click **Sign up** to create an account.
- The floating task window needs Chrome or Edge 116+ (the live site uses HTTPS, so it works).
- If the app has been idle, the first load can take up to a minute while the free-tier server wakes up. 

## Example API Endpoints

The app uses session cookies, so log in first and reuse the cookie. Replace `BASE` with `http://127.0.0.1:5000` locally or your live URL.

```bash
BASE=http://127.0.0.1:5000

# Sign up (also logs you in)
curl -c cookies.txt -X POST $BASE/signup \
  -d "name=Test User" -d "email=test@example.com" \
  -d "password=secret123" -d "confirm_password=secret123"

# Log in (stores the session cookie)
curl -c cookies.txt -X POST $BASE/login-signup \
  -d "email=test@example.com" -d "password=secret123"

# Add a personal task (add -d "list_id=3" to add it to a group instead)
curl -b cookies.txt -X POST $BASE/add-task \
  -d "title=Read chapter 4" -d "description=Notes for class" \
  -d "deadline_date=2026-12-01" -d "deadline_time=17:00" \
  -d "priority=high" -d "category=school"

# Tick / untick a task (awards XP when completed)
curl -b cookies.txt -X POST $BASE/toggle-task/1

# Edit a task
curl -b cookies.txt -X POST $BASE/edit-task/1 \
  -d "title=Read chapter 5" -d "description=" \
  -d "deadline_date=2026-12-02" -d "deadline_time=18:00" \
  -d "priority=medium" -d "category=school"

# Delete a task
curl -b cookies.txt -X DELETE $BASE/delete-task/1

# --- JSON routes (used by the floating window) ---

# Your personal tasks plus level, XP, streak and quest progress
curl -b cookies.txt "$BASE/api/float-tasks?sort=priority"

# Add a task from the floating window
curl -b cookies.txt -X POST $BASE/api/float-tasks/add \
  -d "title=Pay bills" -d "deadline_date=2026-12-05" \
  -d "deadline_time=09:00" -d "priority=low" -d "category=finance"

# Tick / untick a task (JSON with XP messages and the refreshed list)
curl -b cookies.txt -X POST $BASE/api/float-tasks/1/toggle

# Turn "Hide completed" on
curl -b cookies.txt -X POST "$BASE/api/float-tasks/hide-completed?hide=1"

# --- Groups (send X-Requested-With: fetch to get JSON instead of a redirect) ---

# Create a group and invite members by email
curl -b cookies.txt -X POST $BASE/groups/create -H "X-Requested-With: fetch" \
  -d "name=Study Group" -d "emails=friend@example.com"

# Rename a group (owner only)
curl -b cookies.txt -X POST $BASE/groups/1/rename -H "X-Requested-With: fetch" \
  -d "name=Finals Crew"
```

The JSON routes answer with `{"ok": true, "messages": [...], "tasks": [...], "level": ..., "streak": ...}`, or `{"ok": false, "error": "..."}` with a 400 or 404 status when something is wrong. A task you don't own, or a group you are not in, returns **404**. The full list of routes is in the [Routes](#routes) table below.

## How Activity 1 and Activity 2 Were Merged

I did not merge two separate branches. I used `git switch` to create a new branch and move off the **act2** branch and built on top of it, so Activity 2's code already had unique user access and everything else was added as new commits on the same branch.

## Project Structure

```
todolist/
├── app.py                  # Flask app and all routes
├── backend/
│   ├── database.py         # SQLite/Postgres connection, adapter, and all SQL for users, tasks and groups
│   ├── gamification.py     # XP, levels, daily quests, streaks and themes
│   ├── preferences.py      # Small per-user settings (e.g. "Hide completed")
│   └── mailer.py           # Sends the password reset email (Apps Script, Brevo, SMTP, or terminal)
├── webpages/               # HTML templates
│   ├── homepage.html, my_tasks.html, quests.html, groups.html, profile.html
│   ├── login_signup.html, forgot_password.html, reset_password.html
│   ├── landing.html
│   └── sidebar.html        # Navigation, shared by every page after login
├── static/
│   ├── styles/             # my_tasks.css (shared base), sidebar.css, homepage.css, quests.css,
│   │                       # themes.css, profile.css, toasts.css, float.css, float_window.css, ...
│   └── scripts/            # main.js, task_details.js, toasts.js, float.js, groups.js, login_signup.js
├── todolist.db             # SQLite database (local mode only, created automatically)
└── .env                    # Settings and secrets (not in Git)
```

## Database Schema

| Table | Purpose | Main columns |
|-------|---------|--------------|
| `users` | Accounts | `id`, `name`, `email` (unique), `password_hash` |
| `tasks` | Personal or group tasks | `id`, `user_id`, `list_id`, `title`, `description`, `deadline_date`, `deadline_time`, `priority`, `category`, `is_completed` |
| `lists` | Groups | `id`, `name`, `owner_id` |
| `list_members` | Who is in which group | `list_id`, `user_id` |
| `password_resets` | Reset links (only a hash of the token is stored) | `id`, `user_id`, `token_hash`, `expires_at` |
| `xp_events` | Every XP award (task completions, daily quests); a user's XP is the sum of their rows | `id`, `user_id`, `kind`, `ref`, `xp`, `day`, `priority`, `category`, `on_time` |
| `user_prefs` | Each user's saved settings as key/value rows: the picked color theme (`theme`) and the "Hide completed" choice (`hide_completed`) | `user_id`, `key`, `value` |
| `gamification_meta` | Marks one-time jobs as done (e.g. converting old completed tasks to XP) | `key`, `value` |

**How they relate**

- A **user** creates **tasks** (`tasks.user_id`) and owns **lists** (`lists.owner_id`).
- A task with `list_id = NULL` is **personal**: only its creator can see it.
- A task with a `list_id` belongs to that **group**: every member can see and edit it.
- Users and lists are many-to-many through `list_members`. The owner is added there too when the group is created.
- The relationships are enforced in the code, not with `FOREIGN KEY` constraints.

**How XP and levels work**

- The level is not stored. It is calculated from total XP: `level = total XP ÷ 100 (rounded down) + 1`.
- `xp_events` has a unique rule on `(user_id, kind, ref)`, so each task and each daily quest can pay out only once.
- A streak is calculated from the days on which all 3 daily quests were completed. It is not stored either.

## Ownership Checks

The server checks who is asking on every request. It always uses `session["user_id"]`, never an id sent from the browser.

**Tasks.** Every single-task query (get, edit, complete, delete) uses this rule in `backend/database.py`:

```python
ACCESS_CLAUSE = """(
    (tasks.list_id IS NULL AND tasks.user_id = ?)
    OR tasks.list_id IN (SELECT list_id FROM list_members WHERE user_id = ?)
)"""
```

A task is accessible only if it is your own personal task, or it is in a group you belong to. The `?` placeholders are translated to `%s` automatically when running on Postgres.

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
| GET | `/` | Landing page (sends logged-in users to the app) | None |
| GET, POST | `/signup` | Create an account and log in | None |
| GET, POST | `/login-signup` | Log in | None |
| GET | `/logout` | Log out | None |
| GET, POST | `/forgot-password` | Request a reset link | None |
| GET, POST | `/reset-password/<token>` | Set a new password | Valid, unexpired token |
| GET | `/homepage` | Dashboard: stats, due soon, quick add, daily quests | Logged in |
| GET | `/quests` | My Quests: level, streak, daily quests, themes, achievements | Logged in |
| POST | `/theme` | Choose a color theme | Logged in; the theme must be unlocked |
| GET | `/profile` | View profile | Logged in |
| POST | `/profile/name`, `/email`, `/password` | Update profile | Logged in (email and password also need the current password) |
| GET | `/my-tasks` | Your personal tasks | Only your personal tasks are returned |
| GET | `/my-tasks?list=<id>` | A group's tasks | Must be a member, else 404 |
| POST | `/add-task` | Add a task (to a group if `list_id` is sent) | Group: must be a member, else 404 |
| POST | `/edit-task/<id>` | Edit a task | `ACCESS_CLAUSE` |
| POST | `/toggle-task/<id>` | Mark done or not done (awards XP and updates quests when completed) | `ACCESS_CLAUSE` |
| DELETE | `/delete-task/<id>` | Delete a task | `ACCESS_CLAUSE` |
| POST | `/preferences/hide-completed` | Save the "Hide completed" checkbox | Logged in |
| GET | `/api/float-tasks` | Tasks and stats for the floating window (JSON) | Logged in; only your personal tasks |
| POST | `/api/float-tasks/add` | Add a personal task from the floating window (JSON) | Logged in; input is validated |
| POST | `/api/float-tasks/hide-completed` | Save "Hide completed" from the floating window (JSON) | Logged in |
| POST | `/api/float-tasks/<id>/toggle` | Tick or untick a task from the floating window (JSON) | Task must be accessible, else 404 |
| GET | `/groups` | Your groups | Only groups you belong to |
| POST | `/groups/create` | Create a group and invite members by email | Logged in; you become the owner |
| POST | `/groups/<id>/members` | Add a member by email | Member (else 404), then owner |
| POST | `/groups/<id>/rename` | Rename the group | Member (else 404), then owner |
| POST | `/groups/<id>/members/<member_id>/remove` | Remove a member, or leave | Member (else 404). Owner can remove anyone but themselves; others can only remove themselves. The owner can't be removed |
| POST | `/groups/<id>/delete` | Delete the group and its tasks | Member (else 404), then owner |
