from __future__ import annotations

import json
import posixpath
import re
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests


DONE_STATES = {"done", "success", "succeeded", "completed", "complete"}
FAILED_STATES = {"failed", "failure", "error", "canceled", "cancelled"}


class MineruApiError(RuntimeError):
    """Raised when MinerU returns an invalid or failed API response."""


@dataclass(frozen=True)
class ConversionOptions:
    language: str = "ch"
    model_version: str = "vlm"
    enable_formula: bool = True
    enable_table: bool = True
    is_ocr: bool = True
    page_ranges: str | None = None


@dataclass(frozen=True)
class SubmittedTask:
    batch_id: str
    data_id: str
    file_name: str


@dataclass(frozen=True)
class RemoteResult:
    status: str
    raw_status: str
    full_zip_url: str | None = None
    message: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResultFiles:
    markdown: Path | None = None
    docx: Path | None = None
    html: Path | None = None
    zip_file: Path | None = None

    def as_relative_dict(self, root: Path) -> dict[str, str | None]:
        return {
            key: _relative(value, root) if value else None
            for key, value in asdict(self).items()
        }


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def normalize_token(raw: str) -> str:
    token = raw.strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "upload"
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", name, flags=re.UNICODE)
    return name[:160] or "upload"


def _safe_zip_members(zip_path: Path) -> list[tuple[zipfile.ZipInfo, str]]:
    members: list[tuple[zipfile.ZipInfo, str]] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = unquote(info.filename).replace("\\", "/")
            if not name or name.endswith("/") or name.startswith("/"):
                continue
            normalized = posixpath.normpath(name)
            parts = [part for part in normalized.split("/") if part]
            if not parts or parts[0] == "__MACOSX" or any(part in {".", ".."} for part in parts):
                continue
            members.append((info, "/".join(parts)))
    return members


def extract_zip(zip_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info, normalized in _safe_zip_members(zip_path):
            target = out_dir / normalized
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))


def discover_result_files(extract_dir: Path, zip_file: Path | None = None) -> ResultFiles:
    markdowns = sorted(extract_dir.rglob("*.md"), key=lambda p: ("full" not in p.stem.lower(), len(p.parts), p.name))
    docxs = sorted(extract_dir.rglob("*.docx"), key=lambda p: ("full" not in p.stem.lower(), len(p.parts), p.name))
    htmls = sorted(extract_dir.rglob("*.html"), key=lambda p: ("full" not in p.stem.lower(), "index" not in p.stem.lower(), len(p.parts), p.name))
    return ResultFiles(
        markdown=markdowns[0] if markdowns else None,
        docx=docxs[0] if docxs else None,
        html=htmls[0] if htmls else None,
        zip_file=zip_file,
    )


class MineruClient:
    def __init__(self, *, api_token: str, api_base: str, timeout: float = 60.0) -> None:
        self.api_token = normalize_token(api_token)
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        if not self.api_token:
            raise MineruApiError("MINERU_API_TOKEN is not configured")

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = requests.request(method, url, timeout=self.timeout, **kwargs)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            response.raise_for_status()
            raise MineruApiError(f"MinerU returned non-JSON response: {response.text[:300]}") from exc
        response.raise_for_status()

        code = payload.get("code")
        if code not in (0, "0", None):
            message = payload.get("msg") or payload.get("message") or payload
            raise MineruApiError(f"MinerU API error: {message}")
        return payload

    def submit_file(self, file_path: Path, options: ConversionOptions) -> SubmittedTask:
        file_name = safe_filename(file_path.name)
        data_id = uuid.uuid4().hex
        file_payload: dict[str, Any] = {
            "name": file_name,
            "data_id": data_id,
            "is_ocr": options.is_ocr,
        }
        if options.page_ranges:
            file_payload["page_ranges"] = options.page_ranges

        payload = {
            "enable_formula": options.enable_formula,
            "enable_table": options.enable_table,
            "language": options.language,
            "model_version": options.model_version,
            "extra_formats": ["docx", "html"],
            "files": [file_payload],
        }
        body = self._request(
            "POST",
            f"{self.api_base}/file-urls/batch",
            headers=self.headers,
            json=payload,
        )
        data = body.get("data") or {}
        batch_id = str(data.get("batch_id") or "").strip()
        file_urls = data.get("file_urls") or data.get("urls") or []
        if not batch_id or not file_urls:
            raise MineruApiError(f"MinerU did not return batch_id/file_urls: {body}")

        with file_path.open("rb") as f:
            upload_response = requests.put(
                str(file_urls[0]),
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=max(self.timeout, 300),
            )
        upload_response.raise_for_status()
        return SubmittedTask(batch_id=batch_id, data_id=data_id, file_name=file_name)

    def get_result(self, task: SubmittedTask) -> RemoteResult:
        body = self._request(
            "GET",
            f"{self.api_base}/extract-results/batch/{task.batch_id}",
            headers={"Authorization": f"Bearer {self.api_token}"},
        )
        data = body.get("data") or {}
        items = (
            data.get("extract_result")
            or data.get("extract_results")
            or data.get("results")
            or data.get("files")
            or []
        )
        if isinstance(items, dict):
            items = list(items.values())
        if not items:
            return RemoteResult(status="processing", raw_status="waiting", raw=body)

        chosen = self._choose_result_item(items, task)
        raw_status = str(chosen.get("state") or chosen.get("status") or "").strip().lower()
        zip_url = str(chosen.get("full_zip_url") or chosen.get("zip_url") or chosen.get("result_url") or "").strip()
        message = str(chosen.get("err_msg") or chosen.get("message") or chosen.get("msg") or "").strip() or None

        if zip_url or raw_status in DONE_STATES:
            return RemoteResult(status="done", raw_status=raw_status or "done", full_zip_url=zip_url or None, message=message, raw=chosen)
        if raw_status in FAILED_STATES:
            return RemoteResult(status="failed", raw_status=raw_status, message=message or "MinerU task failed", raw=chosen)
        return RemoteResult(status="processing", raw_status=raw_status or "processing", message=message, raw=chosen)

    def _choose_result_item(self, items: list[dict[str, Any]], task: SubmittedTask) -> dict[str, Any]:
        for item in items:
            if str(item.get("data_id") or "") == task.data_id:
                return item
        for item in items:
            if str(item.get("file_name") or item.get("name") or "") == task.file_name:
                return item
        return items[0]

    def download_zip(self, url: str, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=max(self.timeout, 300))
        response.raise_for_status()
        out_path.write_bytes(response.content)
        return out_path


def wait_for_completion(
    client: MineruClient,
    task: SubmittedTask,
    *,
    interval: float = 5.0,
    timeout: float = 1200.0,
) -> RemoteResult:
    deadline = time.monotonic() + timeout
    while True:
        result = client.get_result(task)
        if result.status in {"done", "failed"}:
            return result
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for MinerU batch {task.batch_id}")
        time.sleep(interval)
