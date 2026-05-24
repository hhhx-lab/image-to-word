from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class JobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def manifest_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "job.json"

    def create(self, job_id: str, data: dict[str, Any]) -> dict[str, Any]:
        job_dir = self.job_dir(job_id)
        (job_dir / "upload").mkdir(parents=True, exist_ok=True)
        (job_dir / "result").mkdir(parents=True, exist_ok=True)
        record = {
            **data,
            "id": job_id,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.save(job_id, record)
        return record

    def load(self, job_id: str) -> dict[str, Any]:
        path = self.manifest_path(job_id)
        if not path.exists():
            raise FileNotFoundError(job_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, job_id: str, data: dict[str, Any]) -> dict[str, Any]:
        data["updated_at"] = now_iso()
        path = self.manifest_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        return data

    def update(self, job_id: str, **changes: Any) -> dict[str, Any]:
        data = self.load(job_id)
        data.update(changes)
        return self.save(job_id, data)
