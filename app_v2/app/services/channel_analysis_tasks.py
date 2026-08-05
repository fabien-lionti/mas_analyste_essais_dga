from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_v2.app.db.connection import connect, init_db, now_iso
from app_v2.app.services.channel_structure_service import analyze_channel_structure


@dataclass
class ChannelAnalysisTask:
    task_id: str
    analysis_id: str
    db_path: Path
    options: dict[str, Any]
    status: str = "queued"
    phase: str = "queued"
    processed_files: int = 0
    total_files: int = 0
    percent: float = 0.0
    current_file: str | None = None
    message: str = "En attente"
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "task_id": self.task_id,
                "analysis_id": self.analysis_id,
                "status": self.status,
                "phase": self.phase,
                "processed_files": self.processed_files,
                "total_files": self.total_files,
                "percent": self.percent,
                "current_file": self.current_file,
                "message": self.message,
                "error": self.error,
                "result": self.result,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }

    def update(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self.status = str(payload.get("status") or self.status)
            self.phase = str(payload.get("phase") or self.phase)
            self.processed_files = int(payload.get("processed_files") or self.processed_files)
            self.total_files = int(payload.get("total_files") or self.total_files)
            self.percent = float(payload.get("percent") if payload.get("percent") is not None else self.percent)
            self.current_file = payload.get("current_file", self.current_file)
            self.message = str(payload.get("message") or self.message)
            self.updated_at = now_iso()

    def cancel(self) -> None:
        self._cancel_event.set()
        with self._lock:
            if self.status in {"queued", "running"}:
                self.status = "cancelling"
                self.phase = "cancelling"
                self.message = "Arrêt demandé"
                self.updated_at = now_iso()

    def should_cancel(self) -> bool:
        return self._cancel_event.is_set()


class ChannelAnalysisTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, ChannelAnalysisTask] = {}
        self._lock = threading.Lock()

    def start(self, *, db_path: Path, analysis_id: str, options: dict[str, Any]) -> ChannelAnalysisTask:
        task = ChannelAnalysisTask(
            task_id=f"channel_task_{uuid.uuid4().hex}",
            analysis_id=analysis_id,
            db_path=db_path,
            options=options,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        thread = threading.Thread(target=self._run, args=(task,), daemon=True)
        thread.start()
        return task

    def get(self, task_id: str) -> ChannelAnalysisTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def latest_for_analysis(self, analysis_id: str) -> ChannelAnalysisTask | None:
        with self._lock:
            matches = [task for task in self._tasks.values() if task.analysis_id == analysis_id]
        if not matches:
            return None
        return sorted(matches, key=lambda task: task.created_at)[-1]

    def cancel(self, task_id: str) -> ChannelAnalysisTask | None:
        task = self.get(task_id)
        if task is not None:
            task.cancel()
        return task

    def _run(self, task: ChannelAnalysisTask) -> None:
        task.update({"status": "running", "phase": "opening_db", "message": "Ouverture de la base"})
        try:
            with connect(task.db_path) as conn:
                init_db(conn)
                result = analyze_channel_structure(
                    conn,
                    analysis_id=task.analysis_id,
                    progress_callback=task.update,
                    should_cancel=task.should_cancel,
                    **task.options,
                )
                conn.commit()
            task.update(
                {
                    "status": result["status"],
                    "phase": result["status"],
                    "processed_files": result.get("processed_files", result.get("total_files", 0)),
                    "total_files": result.get("total_files", 0),
                    "percent": 100 if result["status"] == "finished" else task.percent,
                    "message": "Analyse interrompue" if result["status"] == "cancelled" else "Analyse terminée",
                }
            )
            with task._lock:
                task.result = result
                task.updated_at = now_iso()
        except Exception as exc:
            with task._lock:
                task.status = "failed"
                task.phase = "failed"
                task.error = str(exc)
                task.message = "Analyse échouée"
                task.updated_at = now_iso()


channel_analysis_tasks = ChannelAnalysisTaskManager()
