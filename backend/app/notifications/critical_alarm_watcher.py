from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_watcher_task: asyncio.Task | None = None
_watcher_status: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "interval_seconds": None,
    "started_at": None,
    "last_run_at": None,
    "last_success_at": None,
    "last_error_at": None,
    "last_error": None,
    "last_alerts_count": 0,
    "last_critical_threshold_alerts_count": 0,
    "runs_count": 0,
}


def get_critical_alarm_watcher_status() -> dict[str, Any]:
    """Return current critical alarm watcher status."""
    task_done = _watcher_task.done() if _watcher_task is not None else None

    return {
        **_watcher_status,
        "task_exists": _watcher_task is not None,
        "task_done": task_done,
    }


async def run_critical_alarm_watcher_once() -> None:
    """Run one critical alarm watcher iteration."""
    # Local imports avoid circular imports during FastAPI startup.
    from app.analytics.rules_engine import evaluate_channels
    from app.api.routes_alerts import build_current_snapshot
    from app.notifications.email_notifier import (
        is_critical_threshold_alert,
        process_critical_threshold_email_notifications,
    )

    snapshot = await build_current_snapshot(force_refresh=True)
    alerts = evaluate_channels(snapshot["items"], include_normal=True)

    critical_threshold_alerts = [
        alert for alert in alerts if is_critical_threshold_alert(alert)
    ]

    await asyncio.to_thread(
        process_critical_threshold_email_notifications,
        alerts,
    )

    now = datetime.now(timezone.utc).isoformat()

    _watcher_status["last_run_at"] = now
    _watcher_status["last_success_at"] = now
    _watcher_status["last_error"] = None
    _watcher_status["last_alerts_count"] = len(alerts)
    _watcher_status["last_critical_threshold_alerts_count"] = len(critical_threshold_alerts)
    _watcher_status["runs_count"] = int(_watcher_status.get("runs_count") or 0) + 1


async def critical_alarm_watcher_loop() -> None:
    """Continuously check critical threshold alarms in the background."""
    interval_seconds = max(float(settings.critical_alarm_watcher_interval_seconds), 1.0)

    _watcher_status["enabled"] = True
    _watcher_status["running"] = True
    _watcher_status["interval_seconds"] = interval_seconds
    _watcher_status["started_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Critical alarm watcher started with interval %.2f seconds.",
        interval_seconds,
    )

    try:
        while True:
            try:
                await run_critical_alarm_watcher_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                now = datetime.now(timezone.utc).isoformat()
                _watcher_status["last_run_at"] = now
                _watcher_status["last_error_at"] = now
                _watcher_status["last_error"] = str(exc)

                logger.exception("Critical alarm watcher iteration failed: %s", exc)

            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.info("Critical alarm watcher stopped.")
        raise

    finally:
        _watcher_status["running"] = False


async def start_critical_alarm_watcher() -> None:
    """Start the critical alarm watcher if enabled."""
    global _watcher_task

    if not settings.critical_alarm_watcher_enabled:
        _watcher_status["enabled"] = False
        _watcher_status["running"] = False
        _watcher_status["interval_seconds"] = settings.critical_alarm_watcher_interval_seconds
        logger.info("Critical alarm watcher is disabled by settings.")
        return

    if _watcher_task is not None and not _watcher_task.done():
        return

    _watcher_task = asyncio.create_task(critical_alarm_watcher_loop())


async def stop_critical_alarm_watcher() -> None:
    """Stop the critical alarm watcher."""
    global _watcher_task

    if _watcher_task is None:
        return

    _watcher_task.cancel()

    try:
        await _watcher_task
    except asyncio.CancelledError:
        pass

    _watcher_task = None
    _watcher_status["running"] = False