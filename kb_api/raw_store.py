from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from .config import settings


ALLOWED_FOLDERS = [
    "02规章制度与标准规范",
    "03SOP流程化资料_疑似",
    "04表单台账与字段说明_疑似",
    "05岗位职责与角色资料",
    "06安全与应急资料",
    "07信息系统与APP操作",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STAGE_SCRIPTS = {
    "preprocess": REPO_ROOT / "scripts" / "preprocess_raw_02_07.py",
    "chunk": REPO_ROOT / "scripts" / "build_selected_and_chunks.py",
    "embedding": REPO_ROOT / "scripts" / "build_vectors.py",
}

_PIPELINE_LOCK = threading.Lock()
_PIPELINE_THREAD: threading.Thread | None = None


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _iso_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _manifest_default() -> dict:
    return {"files": {}}


def _status_default() -> dict:
    return {
        "running": False,
        "state": "idle",
        "current_stage": "",
        "current_step": "",
        "current_folder": "",
        "run_id": "",
        "trigger_reason": "",
        "started_at": "",
        "updated_at": "",
        "finished_at": "",
        "last_success_at": "",
        "last_error": "",
        "exit_code": None,
    }


def _load_manifest() -> dict:
    return _read_json(settings.raw_manifest_path, _manifest_default())


def _save_manifest(payload: dict) -> None:
    _write_json(settings.raw_manifest_path, payload)


def load_pipeline_status() -> dict:
    return _read_json(settings.raw_pipeline_status_path, _status_default())


def _save_pipeline_status(payload: dict) -> None:
    _write_json(settings.raw_pipeline_status_path, payload)


def _update_pipeline_status(**fields) -> dict:
    with _PIPELINE_LOCK:
        status = load_pipeline_status()
        status.update(fields)
        status["updated_at"] = _now_iso()
        _save_pipeline_status(status)
        return status


def _manifest_key(folder: str, file_name: str) -> str:
    return f"{folder}/{file_name}"


def _sanitize_file_name(file_name: str) -> str:
    return Path(file_name).name


def _validate_folder(folder: str) -> str:
    if folder not in ALLOWED_FOLDERS:
        raise ValueError(f"unsupported folder: {folder}")
    return folder


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _version_archive_path(folder: str, file_name: str, version: str) -> Path:
    return settings.raw_versions_root / folder / _sanitize_file_name(file_name) / version / _sanitize_file_name(file_name)


def _entry_history(entry: dict) -> list[dict]:
    history = entry.get("history")
    if isinstance(history, list):
        return [item for item in history if isinstance(item, dict)]
    return []


def _bootstrap_entry_from_existing_file(folder: str, file_name: str, target: Path) -> dict:
    manifest = _load_manifest()
    files = manifest.setdefault("files", {})
    rel_key = _manifest_key(folder, file_name)
    existing_bytes = target.read_bytes()
    existing_size = len(existing_bytes)
    existing_checksum = _checksum(existing_bytes)
    existing_uploaded_at = _iso_from_timestamp(target.stat().st_mtime)
    entry = {
        "raw_key": rel_key,
        "relative_path": rel_key,
        "folder": folder,
        "file_name": file_name,
        "history": [
            {
                "version": "v1",
                "uploaded_at": existing_uploaded_at,
                "size_bytes": existing_size,
                "checksum": existing_checksum,
                "stored_path": str(target),
            }
        ],
        "current_version": "v1",
        "current_uploaded_at": existing_uploaded_at,
        "current_size_bytes": existing_size,
        "current_checksum": existing_checksum,
        "updated_at": existing_uploaded_at,
        "deleted_at": None,
    }
    files[rel_key] = entry
    _save_manifest(manifest)
    return entry


def _archive_current_version(folder: str, file_name: str, target: Path, entry: dict) -> dict:
    history = _entry_history(entry)
    if not history or not target.exists():
        return entry

    current = history[-1]
    current_version = str(current.get("version", "v1"))
    archive_path = _version_archive_path(folder, file_name, current_version)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, archive_path)
    current["stored_path"] = str(archive_path)
    current["archived_at"] = _now_iso()
    entry["history"] = history
    return entry


def _record_version(
    folder: str,
    file_name: str,
    target: Path,
    data: bytes,
    entry: dict,
    *,
    source_version: str | None,
    restored_from: str | None = None,
    action: str = "upload",
) -> dict:
    target.write_bytes(data)
    history = _entry_history(entry)
    version = f"v{len(history) + 1}"
    uploaded_at = _now_iso()
    checksum = _checksum(data)
    history.append(
        {
            "version": version,
            "uploaded_at": uploaded_at,
            "size_bytes": len(data),
            "checksum": checksum,
            "stored_path": str(target),
            "source_version": source_version,
            "restored_from": restored_from,
            "action": action,
        }
    )
    entry.update(
        {
            "raw_key": _manifest_key(folder, file_name),
            "relative_path": _manifest_key(folder, file_name),
            "folder": folder,
            "file_name": file_name,
            "history": history,
            "current_version": version,
            "current_uploaded_at": uploaded_at,
            "current_size_bytes": len(data),
            "current_checksum": checksum,
            "updated_at": uploaded_at,
            "deleted_at": None,
        }
    )
    manifest = _load_manifest()
    files = manifest.setdefault("files", {})
    files[_manifest_key(folder, file_name)] = entry
    _save_manifest(manifest)
    return entry


def _build_item(path: Path, entry: dict | None) -> dict:
    stat = path.stat()
    active_root = settings.raw_source_root
    try:
        relative = path.resolve().relative_to(active_root.resolve())
    except ValueError:
        relative = None

    if relative and relative.parts:
        folder = relative.parts[0]
    else:
        folder = next((part for part in path.parts if part in ALLOWED_FOLDERS), path.parent.name)
    file_name = path.name
    rel_key = _manifest_key(folder, file_name)
    history = _entry_history(entry or {})
    if history:
        current = history[-1]
        version = str(current.get("version", "v1"))
        upload_time = str(current.get("uploaded_at", _iso_from_timestamp(stat.st_mtime)))
        size_bytes = int(current.get("size_bytes", stat.st_size))
        checksum = current.get("checksum")
    else:
        version = "v1"
        upload_time = _iso_from_timestamp(stat.st_mtime)
        size_bytes = stat.st_size
        checksum = None
        history = [
            {
                "version": version,
                "uploaded_at": upload_time,
                "size_bytes": size_bytes,
                "checksum": checksum,
            }
        ]

    deleted_at = entry.get("deleted_at") if entry else None
    return {
        "raw_key": rel_key,
        "folder": folder,
        "file_name": file_name,
        "relative_path": rel_key,
        "file_path": str(path),
        "exists": True,
        "deleted": bool(deleted_at),
        "version": version,
        "version_count": len(history),
        "upload_time": upload_time,
        "updated_at": entry.get("updated_at", upload_time) if entry else upload_time,
        "size_bytes": size_bytes,
        "checksum": checksum,
        "history": history,
    }


def list_raw_files(include_deleted: bool = False) -> dict:
    manifest = _load_manifest().get("files", {})
    items: list[dict] = []
    for folder in ALLOWED_FOLDERS:
        folder_root = settings.raw_source_root / folder
        if not folder_root.exists():
            continue
        for path in sorted(folder_root.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith(".") or path.name.startswith("~$"):
                continue
            rel_key = _manifest_key(folder, path.name)
            entry = manifest.get(rel_key)
            if entry and entry.get("deleted_at") and not include_deleted and not path.exists():
                continue
            items.append(_build_item(path, entry))
    items.sort(key=lambda item: (item["folder"], item["file_name"]))
    return {
        "total": len(items),
        "allowed_folders": ALLOWED_FOLDERS,
        "raw_file_list": items,
    }


def _update_manifest_for_upload(folder: str, file_name: str, size_bytes: int, checksum: str) -> dict:
    manifest = _load_manifest()
    files = manifest.setdefault("files", {})
    rel_key = _manifest_key(folder, file_name)
    entry = files.get(rel_key) or {
        "raw_key": rel_key,
        "relative_path": rel_key,
        "folder": folder,
        "file_name": file_name,
        "history": [],
    }
    history = _entry_history(entry)
    version = f"v{len(history) + 1}"
    uploaded_at = _now_iso()
    history.append(
        {
            "version": version,
            "uploaded_at": uploaded_at,
            "size_bytes": size_bytes,
            "checksum": checksum,
        }
    )
    entry.update(
        {
            "raw_key": rel_key,
            "relative_path": rel_key,
            "folder": folder,
            "file_name": file_name,
            "history": history,
            "current_version": version,
            "current_uploaded_at": uploaded_at,
            "current_size_bytes": size_bytes,
            "current_checksum": checksum,
            "updated_at": uploaded_at,
            "deleted_at": None,
        }
    )
    files[rel_key] = entry
    _save_manifest(manifest)
    return entry


def _mark_deleted(folder: str, file_name: str) -> dict:
    manifest = _load_manifest()
    files = manifest.setdefault("files", {})
    rel_key = _manifest_key(folder, file_name)
    entry = files.get(rel_key) or {
        "raw_key": rel_key,
        "relative_path": rel_key,
        "folder": folder,
        "file_name": file_name,
        "history": [],
    }
    entry.update(
        {
            "raw_key": rel_key,
            "relative_path": rel_key,
            "folder": folder,
            "file_name": file_name,
            "updated_at": _now_iso(),
            "deleted_at": _now_iso(),
        }
    )
    files[rel_key] = entry
    _save_manifest(manifest)
    return entry


def _raw_path(folder: str, file_name: str) -> Path:
    _validate_folder(folder)
    return settings.raw_source_root / folder / _sanitize_file_name(file_name)


def save_uploaded_files(folder: str, uploads: list[UploadFile]) -> dict:
    _validate_folder(folder)
    target_dir = settings.raw_source_root / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    created_count = 0
    updated_count = 0

    for upload in uploads:
        file_name = _sanitize_file_name(upload.filename or "unnamed")
        target = target_dir / file_name
        existed = target.exists()
        manifest = _load_manifest()
        files = manifest.setdefault("files", {})
        rel_key = _manifest_key(folder, file_name)
        entry = files.get(rel_key)
        if existed and (not entry or not _entry_history(entry)):
            entry = _bootstrap_entry_from_existing_file(folder, file_name, target)
        elif entry is None and existed:
            entry = _bootstrap_entry_from_existing_file(folder, file_name, target)
        elif entry is None:
            entry = {
                "raw_key": rel_key,
                "relative_path": rel_key,
                "folder": folder,
                "file_name": file_name,
                "history": [],
            }
        if existed:
            entry = _archive_current_version(folder, file_name, target, entry)
        payload = upload.file.read()
        if hasattr(payload, "__await__"):
            raise TypeError("async file payload is not supported in sync helper")
        data = payload or b""
        previous_version = str(entry.get("current_version", "v1")) if existed else None
        entry = _record_version(
            folder,
            file_name,
            target,
            data,
            entry,
            source_version=previous_version,
            restored_from=None,
            action="upload",
        )
        results.append(
            {
                "action": "updated" if existed else "created",
                "item": _build_item(target, entry),
            }
        )
        if existed:
            updated_count += 1
        else:
            created_count += 1

    return {
        "uploaded_count": len(results),
        "created_count": created_count,
        "updated_count": updated_count,
        "items": [item["item"] for item in results],
    }


def rollback_raw_file(folder: str, file_name: str, version: str | None = None) -> dict:
    _validate_folder(folder)
    file_name = _sanitize_file_name(file_name)
    target = settings.raw_source_root / folder / file_name
    manifest = _load_manifest()
    files = manifest.setdefault("files", {})
    rel_key = _manifest_key(folder, file_name)
    entry = files.get(rel_key)
    if not entry:
        raise FileNotFoundError(f"raw file manifest not found: {rel_key}")

    history = _entry_history(entry)
    if len(history) < 2:
        raise ValueError("没有可回滚的历史版本")

    if version:
        target_record = next((item for item in history if str(item.get("version")) == version), None)
        if target_record is None:
            raise ValueError(f"未找到版本: {version}")
    else:
        target_record = history[-2]

    source_path = Path(target_record.get("stored_path") or _version_archive_path(folder, file_name, str(target_record.get("version", ""))))
    if not source_path.exists():
        raise FileNotFoundError(f"回滚文件不存在: {source_path}")

    if target.exists():
        entry = _archive_current_version(folder, file_name, target, entry)

    data = source_path.read_bytes()
    restored_from = str(entry.get("current_version", ""))
    entry = _record_version(
        folder,
        file_name,
        target,
        data,
        entry,
        source_version=str(target_record.get("version", "")),
        restored_from=restored_from,
        action="rollback",
    )
    return {
        "restored": True,
        "restored_from_version": str(target_record.get("version", "")),
        "item": _build_item(target, entry),
    }


def delete_raw_file(folder: str, file_name: str) -> dict:
    _validate_folder(folder)
    file_name = _sanitize_file_name(file_name)
    target = settings.raw_source_root / folder / file_name
    existed = target.exists()
    if existed:
        target.unlink()
    entry = _mark_deleted(folder, file_name)
    return {
        "deleted": existed,
        "item": {
            "raw_key": _manifest_key(folder, file_name),
            "folder": folder,
            "file_name": file_name,
            "relative_path": _manifest_key(folder, file_name),
            "file_path": str(target),
            "exists": False,
            "deleted": True,
            "version": str(entry.get("current_version", f"v{len(_entry_history(entry)) or 1}")),
            "version_count": len(_entry_history(entry)) or 1,
            "upload_time": str(entry.get("current_uploaded_at", "")),
            "updated_at": str(entry.get("updated_at", _now_iso())),
            "size_bytes": int(entry.get("current_size_bytes", 0) or 0),
            "checksum": entry.get("current_checksum"),
            "history": _entry_history(entry),
        },
    }


def _append_pipeline_log(text: str) -> None:
    settings.raw_pipeline_log_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.raw_pipeline_log_path.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _run_script(script: Path, stage: str, folder: str | None, env: dict[str, str]) -> None:
    cmd = [sys.executable, str(script)]
    if folder:
        cmd.extend(["--folders", folder])
    _append_pipeline_log(f"[{_now_iso()}] >>> {stage}: {script} folder={folder or 'all'}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True)
    if result.stdout:
        _append_pipeline_log(result.stdout.rstrip("\n"))
    if result.stderr:
        _append_pipeline_log(result.stderr.rstrip("\n"))
    if result.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {result.returncode}")


def _run_pipeline_job(run_id: str, trigger_reason: str, stage: str, folder: str | None) -> None:
    env = os.environ.copy()
    env["KB_ROOT_DIR"] = str(settings.root_dir)
    env["KB_BATCH_ID"] = settings.batch_id
    env["KB_KB_ID"] = settings.knowledge_base_id
    env["PYTHONUNBUFFERED"] = "1"

    try:
        stages = ["preprocess", "chunk", "embedding"] if stage == "all" else [stage]
        for step_name in stages:
            script = PIPELINE_STAGE_SCRIPTS[step_name]
            _update_pipeline_status(current_stage=step_name, current_step=step_name, current_folder=folder or "")
            _run_script(script, step_name, folder, env)

        _update_pipeline_status(
            running=False,
            state="success",
            current_stage=stage,
            current_step="done",
            current_folder=folder or "",
            finished_at=_now_iso(),
            last_success_at=_now_iso(),
            last_error="",
            exit_code=0,
            trigger_reason=trigger_reason,
        )
    except Exception as exc:
        _append_pipeline_log(f"[{_now_iso()}] !!! pipeline failed: {exc}")
        _update_pipeline_status(
            running=False,
            state="failed",
            current_stage=stage,
            current_step="failed",
            current_folder=folder or "",
            finished_at=_now_iso(),
            last_error=str(exc),
            exit_code=1,
            trigger_reason=trigger_reason,
        )


def start_pipeline(stage: str = "all", folder: str | None = None, trigger_reason: str = "manual", force: bool = False) -> dict:
    global _PIPELINE_THREAD
    stage = stage if stage in {"preprocess", "chunk", "embedding", "all"} else "all"
    if folder is not None:
        folder = _validate_folder(folder)
    with _PIPELINE_LOCK:
        status = load_pipeline_status()
        if status.get("running") and not force:
            return status
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        status.update(
            {
                "running": True,
                "state": "running",
                "current_stage": stage,
                "current_step": "queued",
                "current_folder": folder or "",
                "run_id": run_id,
                "trigger_reason": trigger_reason,
                "started_at": _now_iso(),
                "updated_at": _now_iso(),
                "finished_at": "",
                "last_error": "",
                "exit_code": None,
            }
        )
        _save_pipeline_status(status)

        thread = threading.Thread(target=_run_pipeline_job, args=(run_id, trigger_reason, stage, folder), daemon=True)
        _PIPELINE_THREAD = thread
        thread.start()
        return status


def get_pipeline_status() -> dict:
    status = load_pipeline_status()
    status.setdefault("running", False)
    status.setdefault("state", "idle")
    status.setdefault("current_stage", "")
    status.setdefault("current_step", "")
    status.setdefault("current_folder", "")
    status.setdefault("run_id", "")
    status.setdefault("trigger_reason", "")
    status.setdefault("started_at", "")
    status.setdefault("updated_at", "")
    status.setdefault("finished_at", "")
    status.setdefault("last_success_at", "")
    status.setdefault("last_error", "")
    status.setdefault("exit_code", None)
    return status
