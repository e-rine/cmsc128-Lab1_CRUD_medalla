# SideQuest

SideQuest is a gamified to-do list web app. Each person has their own account and private tasks, and people can also create groups to share a task list with others. Finishing tasks earns XP, levels, daily quests, streaks and color themes.

## Features

**Accounts**
- Sign up, log in, log out, and reset a forgotten password by email
- Profile page to change your name, email, and password

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
- **Color themes:** Indigo, Ocean, Forest, Sunset, Rose and Midnight (dark). Pick one on the My Quests page. All themes are unlocked by default; set `UNLOCK_ALL_THEMES = False` in `backend/gamification.py` to unlock one theme every 5 levels instead (levels 5, 10, 15, 20, 25).
- **Achievements:** badges such as First Quest, Task Master, High Roller, Clean Slate, Team Player, Quest Starter, On Fire and Week Warrior, shown on the My Quests page.

**Floating task window**
- "Pop out tasks" in the sidebar opens a small always-on-top window (Chrome or Edge 116+) that stays visible while you use other tabs and apps
- It shows your level, streak and quests, lists your tasks, and lets you tick them off (with a short buffer so a misclick is easy to undo)
- It follows the same "Hide completed" setting and your color theme
- The window stays open as long as the SideQuest tab stays open

**Groups**
- Create a group, add members by email, see members, remove members or leave, and delete the group
- Personal tasks are private, and group tasks are only visible to group members

## Tech Stack

| Part | Choice |
|------|--------|
| Frontend | HTML, CSS, vanilla JavaScript, Flask (Jinja) templates |
| Backend | Flask (Python) |
| Database | SQLite (`todolist.db`) |
| Login | Flask sessions, passwords hashed with Werkzeug |
| Email | SMTP (`smtplib`) |
| Floating window | Document Picture-in-Picture API (browser feature, no library) |

## How Activity 1 and Activity 2 Were Merged

I did not merge two separate branches. I used `git switch` to create a new branch and move off the **act2** branch and built on top of it, so Activity 2's code already had unique user access and everything else was added as new commits on the same branch.


## Project Structure

```
todolist/
├── app.py                  # Flask app and all routes
├── backend/
│   ├── database.py         # All SQL queries for users, tasks and groups
│   ├── gamification.py     # XP, levels, daily quests, streaks and themes
│   └── mailer.py           # Sends the password reset email
├── webpages/               # HTML templates
│   ├── homepage.html, my_tasks.html, quests.html, groups.html, profile.html
│   ├── login_signup.html, forgot_password.html, reset_password.html
│   └── sidebar.html        # Navigation, shared by every page after login
├── static/
│   ├── styles/             # my_tasks.css (shared base), sidebar.css, homepage.css, quests.css,
│   │                       # themes.css, profile.css, toasts.css, float.css, float_window.css, ...
│   └── scripts/            # main.js, task_details.js, toasts.js, float.js, login_signup.js
├── todolist.db             # SQLite database
└── .env                    # Email settings and SECRET_KEY
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

## Configuration

Settings are read from environment variables, which can be put in the `.env` file (it is not in Git):

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Signs the login cookie. Set a long random value (`python -c "import secrets; print(secrets.token_hex(32))"`). If missing, an insecure development key is used. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Email server used for password reset links. If `SMTP_HOST` is not set, the app runs in demo mode and the reset link is printed in the terminal instead of emailed. |

The database tables are created automatically the first time the app starts.

## Database Schema

| Table | Purpose | Main columns |
|-------|---------|--------------|
| `users` | Accounts | `id`, `name`, `email` (unique), `password_hash` |
| `tasks` | Personal or group tasks | `id`, `user_id`, `list_id`, `title`, `description`, `deadline_date`, `deadline_time`, `priority`, `category`, `is_completed` |
| `lists` | Groups | `id`, `name`, `owner_id` |
| `list_members` | Who is in which group | `list_id`, `user_id` |
| `password_resets` | Reset links (only a hash of the token is stored) | `id`, `user_id`, `token_hash`, `expires_at` |
| `xp_events` | Every XP award (task completions, daily quests); a user's XP is the sum of their rows | `id`, `user_id`, `kind`, `ref`, `xp`, `day`, `priority`, `category`, `on_time` |
| `user_settings` | Each user's saved settings: the color theme they picked and the "Hide completed" choice | `user_id`, `theme`, `hide_completed` |
| `gamification_meta` | Marks one-time jobs as done (e.g. converting old completed tasks to XP) | `key`, `value` |

**How they relate**

- A **user** creates **tasks** (`tasks.user_id`) and owns **lists** (`lists.owner_id`).
- A task with `list_id = NULL` is **personal**: only its creator can see it.
- A task with a `list_id` belongs to that **group**: every member can see and edit it.
- Users and lists are many-to-many through `list_members`. The owner is added there too when the group is created.
- The relationships are enforced in the code, not with SQLite `FOREIGN KEY` constraints.

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
| POST | `/api/float-tasks/<id>/toggle` | Tick or untick a task from the floating window (JSON) | Task must be accessible, else 404 |
| GET | `/groups` | Your groups | Only groups you belong to |
| POST | `/groups/create` | Create a group | Logged in; you become the owner |
| POST | `/groups/<id>/members` | Add a member by email | Member (else 404), then owner |
| POST | `/groups/<id>/members/<member_id>/remove` | Remove a member, or leave | Member (else 404). Owner can remove anyone but themselves; others can only remove themselves. The owner can't be removed |
| POST | `/groups/<id>/delete` | Delete the group and its tasks | Member (else 404), then owner |

## Notes

- Password reset links last 30 minutes and only work once.
- `.env` and `todolist.db` are out of Git.
- The floating window needs Chrome or Edge 116+ and a secure address (HTTPS, or `localhost` while developing).
- Completed tasks keep the XP they earned even if they are un-ticked or deleted later.