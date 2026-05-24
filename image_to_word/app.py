from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, get_settings
from .mineru import (
    ConversionOptions,
    MineruApiError,
    MineruClient,
    SubmittedTask,
    discover_result_files,
    extract_zip,
    safe_filename,
)
from .storage import JobStore


settings = get_settings()
store = JobStore(settings.data_dir)
app = FastAPI(title="Image to Word", version="0.1.0")
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


def _client() -> MineruClient:
    return MineruClient(api_token=settings.mineru_api_token, api_base=settings.mineru_api_base)


def _job_or_404(job_id: str) -> dict[str, Any]:
    try:
        return store.load(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


def _path_from_job(job: dict[str, Any], rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    job_dir = store.job_dir(job["id"]).resolve()
    path = (job_dir / rel_path).resolve()
    if job_dir != path and job_dir not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid job path")
    return path


def _response_payload(job: dict[str, Any], include_markdown: bool = True) -> dict[str, Any]:
    files = job.get("files") or {}
    markdown_text = None
    preview_truncated = False
    markdown_path = _path_from_job(job, files.get("markdown"))
    if include_markdown and markdown_path and markdown_path.exists():
        text = markdown_path.read_text(encoding="utf-8", errors="replace")
        preview_truncated = len(text) > settings.preview_limit
        markdown_text = text[: settings.preview_limit]

    downloads = {}
    if files.get("docx"):
        downloads["docx"] = f"/api/jobs/{job['id']}/download/docx"
    if files.get("markdown"):
        downloads["markdown"] = f"/api/jobs/{job['id']}/download/markdown"
    if files.get("zip_file"):
        downloads["zip"] = f"/api/jobs/{job['id']}/download/zip"
    if files.get("html"):
        downloads["html"] = f"/api/jobs/{job['id']}/preview.html"

    return {
        "id": job["id"],
        "status": job["status"],
        "message": job.get("message"),
        "original_filename": job.get("original_filename"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "mineru": job.get("mineru"),
        "files": files,
        "downloads": downloads,
        "markdown": markdown_text,
        "preview_truncated": preview_truncated,
    }


def _finalize_job(job: dict[str, Any], zip_url: str) -> dict[str, Any]:
    job_dir = store.job_dir(job["id"])
    zip_path = job_dir / "result" / "mineru_result.zip"
    extract_dir = job_dir / "result" / "extract"
    client = _client()
    client.download_zip(zip_url, zip_path)
    extract_zip(zip_path, extract_dir)
    result_files = discover_result_files(extract_dir, zip_path)
    files = result_files.as_relative_dict(job_dir)
    return store.update(job["id"], status="done", message="Conversion finished", files=files)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "mineru_configured": bool(settings.mineru_api_token),
        "api_base": settings.mineru_api_base,
    }


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    language: str = Form("ch"),
    model_version: str = Form(settings.mineru_model_version),
    enable_formula: bool = Form(True),
    enable_table: bool = Form(True),
    is_ocr: bool = Form(True),
    page_ranges: str = Form(""),
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    filename = safe_filename(file.filename or "upload")
    job_dir = store.job_dir(job_id)
    upload_path = job_dir / "upload" / filename
    job = store.create(
        job_id,
        {
            "status": "created",
            "message": "Upload received",
            "original_filename": filename,
            "upload_path": f"upload/{filename}",
            "options": {
                "language": language,
                "model_version": model_version,
                "enable_formula": enable_formula,
                "enable_table": enable_table,
                "is_ocr": is_ocr,
                "page_ranges": page_ranges.strip() or None,
            },
            "files": {},
        },
    )

    content = await file.read()
    if not content:
        store.update(job_id, status="failed", message="Uploaded file is empty")
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    upload_path.write_bytes(content)

    options = ConversionOptions(**job["options"])
    try:
        task = await run_in_threadpool(_client().submit_file, upload_path, options)
    except MineruApiError as exc:
        store.update(job_id, status="failed", message=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        store.update(job_id, status="failed", message=f"Failed to submit to MinerU: {exc}")
        raise HTTPException(status_code=502, detail=f"Failed to submit to MinerU: {exc}") from exc

    job = store.update(
        job_id,
        status="processing",
        message="Submitted to MinerU",
        mineru={
            "batch_id": task.batch_id,
            "data_id": task.data_id,
            "file_name": task.file_name,
        },
    )
    return _response_payload(job, include_markdown=False)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _job_or_404(job_id)
    if job["status"] in {"done", "failed"}:
        return _response_payload(job)

    mineru = job.get("mineru")
    if not mineru:
        return _response_payload(job, include_markdown=False)

    task = SubmittedTask(
        batch_id=mineru["batch_id"],
        data_id=mineru["data_id"],
        file_name=mineru["file_name"],
    )
    try:
        remote = await run_in_threadpool(_client().get_result, task)
    except Exception as exc:
        job = store.update(job_id, status="processing", message=f"Waiting for MinerU: {exc}")
        return _response_payload(job, include_markdown=False)

    if remote.status == "failed":
        job = store.update(job_id, status="failed", message=remote.message or "MinerU task failed")
    elif remote.status == "done":
        if not remote.full_zip_url:
            job = store.update(job_id, status="failed", message="MinerU finished without a result zip")
        else:
            job = await run_in_threadpool(_finalize_job, job, remote.full_zip_url)
    else:
        job = store.update(job_id, status="processing", message=remote.raw_status or "Processing")
    return _response_payload(job)


@app.get("/api/jobs/{job_id}/download/{kind}")
def download(job_id: str, kind: str) -> FileResponse:
    job = _job_or_404(job_id)
    files = job.get("files") or {}
    aliases = {"zip": "zip_file", "markdown": "markdown", "docx": "docx"}
    key = aliases.get(kind)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown download type")
    path = _path_from_job(job, files.get(key))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"{kind} is not available")

    filename = path.name
    if kind == "docx":
        filename = f"{Path(job.get('original_filename') or 'result').stem}.docx"
    if kind == "markdown":
        filename = f"{Path(job.get('original_filename') or 'result').stem}.md"
    return FileResponse(path, filename=filename)


@app.get("/api/jobs/{job_id}/preview.html", response_class=HTMLResponse)
def html_preview(job_id: str) -> HTMLResponse:
    job = _job_or_404(job_id)
    path = _path_from_job(job, (job.get("files") or {}).get("html"))
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="HTML preview is not available")
    html = path.read_text(encoding="utf-8", errors="replace")
    base = f'<base href="/api/jobs/{job_id}/asset/">'
    if "<head" in html.lower():
        html = html.replace("<head>", f"<head>{base}", 1)
    else:
        html = f"{base}\n{html}"
    return HTMLResponse(html)


@app.get("/api/jobs/{job_id}/asset/{asset_path:path}")
def asset(job_id: str, asset_path: str) -> FileResponse:
    job = _job_or_404(job_id)
    html_path = _path_from_job(job, (job.get("files") or {}).get("html"))
    if not html_path:
        raise HTTPException(status_code=404, detail="No extracted assets")
    base_dir = html_path.parent.resolve()
    path = (base_dir / asset_path).resolve()
    if base_dir != path and base_dir not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid asset path")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(path)
