# Sends the email to the user

import json
import os
import smtplib
import urllib.request
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
if os.environ.get("APPS_SCRIPT_URL"):
    print("[mailer] Email ON: sending through your Google Apps Script (Gmail)", flush=True)
elif os.environ.get("BREVO_API_KEY"):
    print(f"[mailer] Email ON: sending through Brevo as {os.environ.get('MAIL_FROM', '(MAIL_FROM not set)')}", flush=True)
elif os.environ.get("SMTP_HOST"):
    print(f"[mailer] Email ON: sending through {os.environ['SMTP_HOST']} as {os.environ.get('SMTP_USER', '(no user set)')}", flush=True)
else:
    print("[mailer] Email OFF: no SMTP_HOST found (looked for .env next to app.py). Reset links will only print in this terminal.", flush=True)


def _send_with_apps_script(to_email, name, reset_link, minutes):
    """Sends through a tiny Google Apps Script web app that uses your Gmail (HTTPS, works on Render's free tier)."""
    payload = {
        "secret": os.environ.get("APPS_SCRIPT_SECRET", ""),
        "to": to_email,
        "subject": "Reset your SideQuest password",
        "body": (
            f"Hi {name},\n\n"
            f"We got a request to reset your SideQuest password. "
            f"Open this link to choose a new one (it expires in {minutes} minutes and works once):\n\n"
            f"{reset_link}\n\n"
            f"If you didn't ask for this, you can ignore this email. Your password won't change."
        ),
    }
    request = urllib.request.Request(
        os.environ["APPS_SCRIPT_URL"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "text/plain"},     # text/plain avoids a CORS-style preflight on Google's side
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:       # Google answers with a redirect; urllib follows it
        return response.read().decode("utf-8", "replace").strip() == "ok"


def _send_with_brevo(to_email, name, reset_link, minutes):
    """Sends over HTTPS (port 443), which works on hosts that block SMTP ports, like Render's free tier."""
    payload = {
        "sender": {"name": "SideQuest", "email": os.environ["MAIL_FROM"]},
        "to": [{"email": to_email, "name": name}],
        "subject": "Reset your SideQuest password",
        "textContent": (
            f"Hi {name},\n\n"
            f"We got a request to reset your SideQuest password. "
            f"Open this link to choose a new one (it expires in {minutes} minutes and works once):\n\n"
            f"{reset_link}\n\n"
            f"If you didn't ask for this, you can ignore this email. Your password won't change."
        ),
    }
    request = urllib.request.Request(
        os.environ.get("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": os.environ["BREVO_API_KEY"],
            "content-type": "application/json",
            "accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return 200 <= response.status < 300


def send_reset_email(to_email, name, reset_link, minutes):
    """Returns True if a real email was sent, False if it fell back to the terminal."""
    if os.environ.get("APPS_SCRIPT_URL"):
        try:
            if _send_with_apps_script(to_email, name, reset_link, minutes):
                print(f"[mailer] Email sent to {to_email} (Apps Script)", flush=True)
                return True
            print("[mailer] Apps Script did not accept the email (wrong secret or script error); showing the link here instead.", flush=True)
        except Exception as error:
            print(f"[mailer] Apps Script send failed ({error}); showing the link here instead.", flush=True)

    if os.environ.get("BREVO_API_KEY") and os.environ.get("MAIL_FROM"):
        try:
            if _send_with_brevo(to_email, name, reset_link, minutes):
                print(f"[mailer] Email sent to {to_email} (Brevo)", flush=True)
                return True
        except Exception as error:      # fall back so the flow still works
            print(f"[mailer] Brevo send failed ({error}); showing the link here instead.", flush=True)

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

    if not host and not os.environ.get("BREVO_API_KEY") and not os.environ.get("APPS_SCRIPT_URL"):
        print("[mailer] No email service is set up, so no real email is sent. Add BREVO_API_KEY and MAIL_FROM (or SMTP_HOST) to enable email.")
    print(
        "\n========== PASSWORD RESET (demo mode: email not sent) ==========\n"
        f"To:   {to_email}\n"
        f"Link: {reset_link}\n"
        f"(valid for {minutes} minutes, single use)\n"
        "================================================================\n",
        flush=True,
    )
    return False