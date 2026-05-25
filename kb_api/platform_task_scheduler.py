from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import settings
from .operation_log import append_operation_event
from .platform_tasks import build_task_due_report, build_task_weekly_report, write_task_due_report, write_task_weekly_report


_SCHEDULER_LOCK = threading.Lock()
_SCHEDULER_THREAD: threading.Thread | None = None


def _now() -> datetime:
    return datetime.now().astimezone()


def _scheduled_time() -> tuple[int, int]:
    raw = str(getattr(settings, "platform_task_report_run_time", "00:20"))
    try:
        hour, minute = raw.split(":", 1)
        return max(0, min(23, int(hour))), max(0, min(59, int(minute)))
    except Exception:
        return 0, 20


def _status_path(root_dir: Path | str) -> Path:
    return Path(root_dir) / "operations" / "platform_task_report_automation.json"


def _status_default() -> dict:
    return {
        "running": False,
        "thread_started": False,
        "scheduled_time": f"{_scheduled_time()[0]:02d}:{_scheduled_time()[1]:02d}",
        "check_interval_seconds": int(getattr(settings, "platform_task_report_check_interval_seconds", 60)),
        "timezone": "Asia/Shanghai",
        "last_checked_at": "",
        "last_attempted_date": "",
        "last_success_date": "",
        "last_success_at": "",
        "last_error": "",
        "last_run_started_at": "",
        "last_run_finished_at": "",
        "pending_dates": [],
        "next_planned_date": "",
        "last_due_report_path": "",
        "last_weekly_report_path": "",
    }


def _read_status(path: Path) -> dict:
    if not path.exists():
        return _status_default()
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            data = _status_default()
            data.update(payload)
            return data
    except Exception:
        pass
    return _status_default()


def _write_status(path: Path, payload: dict) -> dict:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_platform_task_report_automation_status(root_dir: Path | str) -> dict:
    return _read_status(_status_path(root_dir))


def _save_platform_task_report_automation_status(root_dir: Path | str, payload: dict) -> dict:
    return _write_status(_status_path(root_dir), payload)


def _pending_dates(status: dict, now: datetime) -> list[str]:
    scheduled_hour, scheduled_minute = _scheduled_time()
    scheduled_today = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
    yesterday = now.date() - timedelta(days=1)
    last_success = str(status.get("last_success_date") or "").strip()
    start_date = None
    if last_success:
        try:
            start_date = datetime.fromisoformat(last_success).date() + timedelta(days=1)
        except ValueError:
            start_date = None
    if start_date is None:
        start_date = yesterday

    if start_date > yesterday:
        return []

    pending: list[str] = []
    current = start_date
    while current <= yesterday:
        if current < yesterday or now >= scheduled_today:
            pending.append(current.isoformat())
        current += timedelta(days=1)
    return pending


def run_platform_task_report_automation(root_dir: Path | str, report_date: str | None = None, force: bool = False) -> dict:
    root_dir = Path(root_dir)
    now = _now()
    status = load_platform_task_report_automation_status(root_dir)
    status["last_checked_at"] = now.isoformat(timespec="seconds")
    status["running"] = True
    status["last_run_started_at"] = now.isoformat(timespec="seconds")
    pending = [report_date] if report_date else _pending_dates(status, now)
    status["pending_dates"] = pending
    if pending:
        status["next_planned_date"] = pending[0]
    _save_platform_task_report_automation_status(root_dir, status)

    results: list[dict] = []
    try:
        for day in pending:
            if not day:
                continue
            append_operation_event(
                root_dir,
                event_type="platform_task_report_auto_trigger",
                knowledge_base_id="platform_run_memory",
                source="scheduler/platform-task-report",
                actor="system",
                params={"report_date": day, "force": force},
                status="running",
                remark="platform task report auto trigger",
            )
            due_payload = build_task_due_report(root_dir, event_date=day)
            weekly_payload = build_task_weekly_report(root_dir, event_date=day)
            due_report_path = str(write_task_due_report(root_dir, event_date=day))
            weekly_report_path = str(write_task_weekly_report(root_dir, event_date=day))
            results.append(
                {
                    "report_date": day,
                    "due_report_path": due_report_path,
                    "weekly_report_path": weekly_report_path,
                    "due_total": len(due_payload["overdue"]) + len(due_payload["due_soon"]) + len(due_payload["no_due"]),
                    "weekly_total": weekly_payload["total"],
                }
            )
            status["last_success_date"] = day
            status["last_success_at"] = now.isoformat(timespec="seconds")
            status["last_attempted_date"] = day
            status["last_error"] = ""
            status["last_due_report_path"] = due_report_path
            status["last_weekly_report_path"] = weekly_report_path
            append_operation_event(
                root_dir,
                event_type="platform_task_report_auto_success",
                knowledge_base_id="platform_run_memory",
                source="scheduler/platform-task-report",
                actor="system",
                params={
                    "report_date": day,
                    "due_report_path": due_report_path,
                    "weekly_report_path": weekly_report_path,
                },
                status="success",
                remark="platform task report auto success",
            )
        status["pending_dates"] = []
        status["next_planned_date"] = ""
        status["last_run_finished_at"] = _now().isoformat(timespec="seconds")
        status["running"] = False
        _save_platform_task_report_automation_status(root_dir, status)
        return {
            "running": False,
            "scheduled_time": status["scheduled_time"],
            "pending_dates": [],
            "results": results,
            "last_success_date": status.get("last_success_date", ""),
            "last_success_at": status.get("last_success_at", ""),
            "last_error": "",
            "last_checked_at": status.get("last_checked_at", ""),
            "last_due_report_path": status.get("last_due_report_path", ""),
            "last_weekly_report_path": status.get("last_weekly_report_path", ""),
        }
    except Exception as exc:
        status["last_error"] = str(exc)
        status["last_run_finished_at"] = _now().isoformat(timespec="seconds")
        status["running"] = False
        _save_platform_task_report_automation_status(root_dir, status)
        append_operation_event(
            root_dir,
            event_type="platform_task_report_auto_failed",
            knowledge_base_id="platform_run_memory",
            source="scheduler/platform-task-report",
            actor="system",
            params={"report_date": report_date or "", "pending_dates": pending},
            status="failed",
            error_message=str(exc),
            remark="platform task report auto failed",
        )
        raise


def _scheduler_loop(root_dir: Path | str) -> None:
    interval = max(15, int(getattr(settings, "platform_task_report_check_interval_seconds", 60)))
    while True:
        try:
            now = _now()
            status = load_platform_task_report_automation_status(root_dir)
            pending = _pending_dates(status, now)
            status["last_checked_at"] = now.isoformat(timespec="seconds")
            status["pending_dates"] = pending
            status["next_planned_date"] = pending[0] if pending else ""
            status["running"] = False
            _save_platform_task_report_automation_status(root_dir, status)
            if pending:
                run_platform_task_report_automation(root_dir)
        except Exception:
            pass
        time.sleep(interval)


def ensure_platform_task_report_scheduler_started(root_dir: Path | str) -> dict:
    global _SCHEDULER_THREAD
    with _SCHEDULER_LOCK:
        status = load_platform_task_report_automation_status(root_dir)
        status["thread_started"] = bool(_SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive())
        if _SCHEDULER_THREAD and _SCHEDULER_THREAD.is_alive():
            _save_platform_task_report_automation_status(root_dir, status)
            return status
        thread = threading.Thread(target=_scheduler_loop, args=(root_dir,), daemon=True)
        _SCHEDULER_THREAD = thread
        status["thread_started"] = True
        status["last_checked_at"] = _now().isoformat(timespec="seconds")
        _save_platform_task_report_automation_status(root_dir, status)
        thread.start()
        return status
