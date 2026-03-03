"""Run manifest helpers for traceability, resumability, and auditability."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunManifest:
    """Thread-safe manifest recorder for one pipeline run."""

    project_root: Path
    run_id: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._records = 0
        self._success = 0
        self._failed = 0
        self._skipped = 0
        self.manifest_dir = self.project_root / "logs" / "manifests"
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.manifest_dir / f"run_{self.run_id}.jsonl"
        self.summary_path = self.manifest_dir / f"run_{self.run_id}_summary.json"

    def record_stage_event(self, stage: str, event: str, message: str) -> None:
        payload = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "type": "stage_event",
            "stage": stage,
            "event": event,
            "message": message,
        }
        self._append(payload)

    def record_file_result(
        self,
        *,
        stage: str,
        class_name: str,
        input_file: Path,
        status: str,
        output_files: Iterable[Path] = (),
        retries: int = 0,
        message: str | None = None,
        error_type: str | None = None,
    ) -> None:
        output_paths = [str(path) for path in output_files]
        payload = {
            "ts": _utc_now(),
            "run_id": self.run_id,
            "type": "file_result",
            "stage": stage,
            "class_name": class_name,
            "input_file": str(input_file),
            "status": status,
            "retries": retries,
            "output_files": output_paths,
        }
        if message:
            payload["message"] = message
        if error_type:
            payload["error_type"] = error_type
        self._append(payload)

    def finalize(self) -> None:
        summary = {
            "run_id": self.run_id,
            "generated_at": _utc_now(),
            "records": self._records,
            "success": self._success,
            "failed": self._failed,
            "skipped": self._skipped,
            "events_file": str(self.events_path),
        }
        with self.summary_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)

    def _append(self, payload: dict) -> None:
        with self._lock:
            if payload.get("type") == "file_result":
                status = payload.get("status")
                if status == "success":
                    self._success += 1
                elif status == "failed":
                    self._failed += 1
                elif status == "skipped":
                    self._skipped += 1
            self._records += 1
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
