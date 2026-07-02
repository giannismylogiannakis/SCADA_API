from __future__ import annotations

import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from typing import Any

from app.core.config import settings
from app.settings.repository import (
    load_active_email_notification_state_records,
    load_email_notification_settings_record,
    save_email_notification_state,
    utc_now_iso,
)

logger = logging.getLogger(__name__)
_notification_processing_lock = threading.Lock()

CRITICAL_THRESHOLD_RULE_IDS = {
    "threshold_critical_low",
    "threshold_critical_high",
}


def is_smtp_configured() -> bool:
    """Return true if SMTP settings are present."""
    return bool(
        settings.email_notifications_smtp_host
        and settings.email_notifications_smtp_username
        and settings.email_notifications_smtp_password
    )


def get_notification_key(alert: dict[str, Any]) -> str:
    """Build a stable notification key for anti-spam tracking."""
    return f"{alert.get('cnl_num')}:{alert.get('rule_id')}"


def is_critical_threshold_alert(alert: dict[str, Any]) -> bool:
    """Return true only for critical static threshold alerts."""
    if alert.get("severity") != "critical":
        return False

    if alert.get("dashboard_visible") is False:
        return False

    rule_id = str(alert.get("rule_id") or "").strip()

    if rule_id not in CRITICAL_THRESHOLD_RULE_IDS:
        return False

    metrics = alert.get("metrics")
    threshold_key = ""

    if isinstance(metrics, dict):
        threshold_key = str(metrics.get("threshold_key") or "").strip()

    return threshold_key in {"critical_low", "critical_high"}


def format_alert_value(alert: dict[str, Any]) -> str:
    """Format current value with unit for email body."""
    value = alert.get("current_value")
    unit = alert.get("unit") or ""

    if value is None or value == "":
        return "—"

    return f"{value} {unit}".strip()


def build_email_subject(alert: dict[str, Any]) -> str:
    """Build Greek email subject."""
    channel_name = alert.get("display_name") or alert.get("channel_name") or f"Κανάλι {alert.get('cnl_num')}"
    prefix = settings.email_notifications_subject_prefix or "Rapid SCADA"

    return f"[{prefix}] Κρίσιμο όριο: {channel_name}"


def build_email_body(alert: dict[str, Any]) -> str:
    """Build Greek plain-text email body."""
    metrics = alert.get("metrics") if isinstance(alert.get("metrics"), dict) else {}
    threshold_key = metrics.get("threshold_key") or "—"
    threshold_value = metrics.get("threshold_value")
    threshold_label = {
        "critical_low": "Κρίσιμο χαμηλό όριο",
        "critical_high": "Κρίσιμο υψηλό όριο",
    }.get(str(threshold_key), str(threshold_key))

    channel_name = alert.get("display_name") or alert.get("channel_name") or f"Κανάλι {alert.get('cnl_num')}"
    category_label = alert.get("category_label") or alert.get("category") or "—"

    return "\n".join(
        [
            "Ενεργοποιήθηκε κρίσιμη προειδοποίηση ορίου.",
            "",
            f"Κανάλι: {channel_name}",
            f"Αριθμός καναλιού: {alert.get('cnl_num')}",
            f"Κατηγορία: {category_label}",
            f"Τρέχουσα τιμή: {format_alert_value(alert)}",
            f"Όριο: {threshold_label}",
            f"Τιμή ορίου: {threshold_value if threshold_value is not None else '—'}",
            f"Λόγος: {alert.get('reason') or '—'}",
            f"Χρόνος ανάγνωσης: {alert.get('fetched_at') or '—'}",
            "",
            "Το email στάλθηκε μία φορά για αυτή την παραβίαση.",
            "Νέο email θα σταλεί μόνο αν η τιμή επανέλθει πρώτα εντός ορίου και μετά ξαναπαραβιάσει το κρίσιμο όριο.",
        ]
    )


def send_email(
    *,
    recipients: list[str],
    subject: str,
    body: str,
) -> None:
    """Send one plain text email through configured SMTP."""
    sender = settings.email_notifications_from or settings.email_notifications_smtp_username

    if not sender:
        raise RuntimeError("Δεν έχει οριστεί email sender.")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    smtp_host = settings.email_notifications_smtp_host
    smtp_port = settings.email_notifications_smtp_port

    if not smtp_host:
        raise RuntimeError("Δεν έχει οριστεί SMTP host.")

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        if settings.email_notifications_use_tls:
            smtp.starttls(context=context)

        smtp.login(
            settings.email_notifications_smtp_username,
            settings.email_notifications_smtp_password,
        )
        smtp.send_message(message)


def process_critical_threshold_email_notifications(alerts: list[dict[str, Any]]) -> None:
    """
    Send email notifications for critical threshold alerts.

    Anti-spam rule:
    - Send once when a critical threshold alert becomes active.
    - Do not send again while the same channel/rule remains active.
    - Reset when the channel/rule is no longer active.

    A process-level lock avoids duplicate emails if the dashboard endpoint and
    the background watcher run at the same time.
    """
    if not _notification_processing_lock.acquire(blocking=False):
        logger.info("Critical threshold email notification processing is already running.")
        return

    try:
        record = load_email_notification_settings_record()
        notification_settings = record.get("settings", {})

        if not notification_settings.get("enabled"):
            return

        recipients = notification_settings.get("recipients")

        if not isinstance(recipients, list) or not recipients:
            return

        if not is_smtp_configured():
            logger.warning("Email notifications enabled but SMTP is not configured.")
            return

        active_state_records = load_active_email_notification_state_records()

        current_alerts_by_key = {
            get_notification_key(alert): alert
            for alert in alerts
            if is_critical_threshold_alert(alert)
        }

        now = utc_now_iso()

        for notification_key, alert in current_alerts_by_key.items():
            previous_state = active_state_records.get(notification_key)

            state = {
                "notification_key": notification_key,
                "cnl_num": alert.get("cnl_num"),
                "rule_id": alert.get("rule_id"),
                "rule_type": alert.get("rule_type"),
                "display_name": alert.get("display_name") or alert.get("channel_name"),
                "reason": alert.get("reason"),
                "current_value": alert.get("current_value"),
                "unit": alert.get("unit"),
                "last_alert_at": now,
            }

            if previous_state:
                save_email_notification_state(
                    notification_key,
                    {
                        **previous_state.get("state", {}),
                        **state,
                    },
                    active=True,
                )
                continue

            try:
                send_email(
                    recipients=recipients,
                    subject=build_email_subject(alert),
                    body=build_email_body(alert),
                )
            except Exception as exc:
                logger.exception(
                    "Failed to send critical threshold email for %s: %s",
                    notification_key,
                    exc,
                )
                continue

            save_email_notification_state(
                notification_key,
                {
                    **state,
                    "first_sent_at": now,
                    "last_sent_at": now,
                },
                active=True,
            )

        for notification_key, state_record in active_state_records.items():
            if notification_key in current_alerts_by_key:
                continue

            previous_state = state_record.get("state", {})
            recovered_state = {
                **previous_state,
                "last_recovered_at": now,
            }

            save_email_notification_state(
                notification_key,
                recovered_state,
                active=False,
            )

    finally:
        _notification_processing_lock.release()