import os
import smtplib
import ssl
import sqlite3
import datetime as dt
from email.message import EmailMessage
from typing import Dict, Iterable, Optional

from .settings import get_latest_settings
from .gen_message import build_alert_message


# ---------------------------------------------------------------------------
# Hardcoded SMTP configuration (edit these values)
# ---------------------------------------------------------------------------

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USERNAME = "saulfernandemil@gmail.com"
SMTP_PASSWORD = "tikl bpnp yayx xxxb"   # <-- replace locally
SMTP_SENDER   = SMTP_USERNAME


class EmailConfigError(RuntimeError):
    """Raised when email configuration is missing or invalid."""


# Database file for alert logs
ALERT_DB_PATH = os.path.join(os.path.dirname(__file__), "alerts.db")


# ---------------------------------------------------------------------------
# Hardcoded SMTP loader
# ---------------------------------------------------------------------------

def _get_smtp_config() -> Dict[str, object]:
    """
    Return the hardcoded SMTP configuration.
    """
    return {
        "host": SMTP_HOST,
        "port": SMTP_PORT,
        "username": SMTP_USERNAME,
        "password": SMTP_PASSWORD,
        "use_tls": True,
        "sender": SMTP_SENDER,
    }


# ---------------------------------------------------------------------------
# Alert log database functions
# ---------------------------------------------------------------------------

def _ensure_alert_log_table() -> None:
    """
    Ensure alerts.db + email_alert_logs table exist.
    """
    with sqlite3.connect(ALERT_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_alert_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                recipient TEXT NOT NULL,
                alert_msg TEXT NOT NULL
            )
            """
        )
        conn.commit()


def log_email_alert(recipient: str, alert_msg: str) -> None:
    """
    Log each successful email alert into alerts.db.
    """
    _ensure_alert_log_table()
    ts = dt.datetime.utcnow().isoformat()

    with sqlite3.connect(ALERT_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO email_alert_logs (ts, recipient, alert_msg)
            VALUES (?, ?, ?)
            """,
            (ts, recipient, alert_msg),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Email sender
# ---------------------------------------------------------------------------

def send_email(
    to_address: str,
    subject: str,
    plain_text: str,
    html_body: Optional[str] = None,
) -> None:
    """
    Sends an email using the hardcoded SMTP settings above.
    """
    config = _get_smtp_config()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["sender"]
    msg["To"] = to_address

    msg.set_content(plain_text)

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()

    with smtplib.SMTP(config["host"], config["port"]) as server:
        server.starttls(context=context)
        server.login(config["username"], config["password"])
        server.send_message(msg)


# ---------------------------------------------------------------------------
# Spike alert logic entrypoint
# ---------------------------------------------------------------------------

def send_spike_alert_if_enabled(
    spiking_sensors: Iterable[str],
    metrics: Optional[Dict[str, float]] = None,
    aqi_trend: Optional[Dict[str, float]] = None,
    forecast_window_minutes: Optional[int] = None,
) -> bool:
    """
    Called when a spike is detected.

    Uses:
      - hardcoded SMTP settings above
      - latest settings from resources/settings.db:
          * email
          * notifications (bool)
      - logs each alert into alerts.db
    """
    settings = get_latest_settings()
    if not settings:
        print("send_spike_alert_if_enabled: no settings found")
        return False

    # Example settings structure:
    # {
    #   "email": "deceiver023@gmail.com",
    #   "forecast_duration": 30,
    #   "notifications": True,
    #   "refresh_rate": 5,
    #   "ts": 1764739129
    # }

    recipient = settings.get("email")
    notifications_enabled = bool(settings.get("notifications"))

    if not recipient:
        print("send_spike_alert_if_enabled: no user email in settings")
        return False

    if not notifications_enabled:
        print("send_spike_alert_if_enabled: notifications disabled")
        return False

    try:
        subject, plain_body, html_body = build_alert_message(
            spiking_sensors=spiking_sensors,
            metrics=metrics,
            aqi_trend=aqi_trend,
            forecast_window_minutes=forecast_window_minutes,
        )

        send_email(
            to_address=recipient,
            subject=subject,
            plain_text=plain_body,
            html_body=html_body,
        )

        # Log to alerts.db
        try:
            log_email_alert(recipient=recipient, alert_msg=plain_body)
        except Exception as log_err:
            print("Failed to log alert:", log_err)

        return True

    except Exception as e:
        print("send_spike_alert_if_enabled error:", e)
        return False
