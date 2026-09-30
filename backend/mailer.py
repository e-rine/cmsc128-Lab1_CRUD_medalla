"""Sends the password-reset email.

Put this file in the backend/ folder (next to database.py).

Two modes:
  * SMTP mode  - if the SMTP_HOST environment variable is set, a real email is sent.
  * Demo mode  - otherwise the reset link is printed in the terminal running the app.
                 (Fine for local development and demos; NOT secure for production.)

Settings can go in a file named .env in the project folder (next to app.py):

  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=you@gmail.com
  SMTP_PASSWORD=your-16-character-app-password
  SMTP_FROM=you@gmail.com

or be set as normal environment variables. Never commit the .env file.
"""
import os
import smtplib
from email.message import EmailMessage


def _load_env_file():
    """Tiny .env reader (no extra packages). Real environment variables win."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

# Shown once when the app starts, so you can see straight away which mode is on.
if os.environ.get("SMTP_HOST"):
    print(f"[mailer] Email ON: sending through {os.environ['SMTP_HOST']} as {os.environ.get('SMTP_USER', '(no user set)')}", flush=True)
else:
    print("[mailer] Email OFF: no SMTP_HOST found (looked for .env next to app.py). Reset links will only print in this terminal.", flush=True)


def send_reset_email(to_email, name, reset_link, minutes):
    """Returns True if a real email was sent, False if it fell back to the terminal."""
    host = os.environ.get("SMTP_HOST")

    if host:
        try:
            msg = EmailMessage()
            msg["Subject"] = "Reset your SideQuest password"
            msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "no-reply@sidequest.local"
            msg["To"] = to_email
            msg.set_content(
                f"Hi {name},\n\n"
                f"We got a request to reset your SideQuest password. "
                f"Open this link to choose a new one (it expires in {minutes} minutes and works once):\n\n"
                f"{reset_link}\n\n"
                f"If you didn't ask for this, you can ignore this email. Your password won't change."
            )
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", 587)), timeout=10) as server:
                server.starttls()
                user = os.environ.get("SMTP_USER")
                if user:
                    password = os.environ.get("SMTP_PASSWORD", "")
                    if "gmail" in host:
                        password = password.replace(" ", "")   # Google shows app passwords with spaces
                    server.login(user, password)
                server.send_message(msg)
            print(f"[mailer] Email sent to {to_email}", flush=True)
            return True
        except Exception as error:      # fall back so the flow still works
            print(f"[mailer] SMTP send failed ({error}); showing the link here instead.")

    if not host:
        print("[mailer] SMTP_HOST is not set, so no real email is sent. Add it to your .env file to enable email.")
    print(
        "\n========== PASSWORD RESET (demo mode: email not sent) ==========\n"
        f"To:   {to_email}\n"
        f"Link: {reset_link}\n"
        f"(valid for {minutes} minutes, single use)\n"
        "================================================================\n",
        flush=True,
    )
    return False