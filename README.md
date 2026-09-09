# SideQuest

SideQuest is a gamified Todo List web app that engages users accomplish quests and achievements by finishing their tasks.

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript (vanilla)
- **Backend:** Flask (Python)
- **Database:** SQLite

**Why this stack:** Flask is lightweight and pairs naturally with Python, keeping the whole project in one language. SQLite needs no separate server, account, or API keys it's built into Python and stores everything in a single file, which is more than enough for a small, single-user CRUD app like this.

## Running It Locally

**Requirements:** Python 3 installed.

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd todolist

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1      # Windows PowerShell
# source venv/bin/activate     # Mac/Linux

# 3. Install dependencies
pip install flask

# 4. Run the app
python app.py
```

Then open **http://127.0.0.1:5000/** in your browser.

The SQLite database file is created automatically the first time you run the app — no manual setup needed.

## CRUD Operations (Routes)

All data operations happen through Flask routes, which read/write to SQLite via functions in `backend/database.py`.

| Method | Route | Operation | What it does |
|--------|-------|-----------|--------------|
| GET | `/my-tasks` | Read | View all tasks |
| POST | `/add-task` | Create | Add a new task |
| POST | `/edit-task/<id>` | Update | Edit an existing task |
| POST | `/delete-task/<id>` | Delete | Remove a task |
| POST | `/toggle-task/<id>` | Update | Mark a task done / not done |