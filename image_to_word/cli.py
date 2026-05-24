from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import uvicorn

from .config import PROJECT_ROOT, get_settings
from .mineru import ConversionOptions, MineruClient, discover_result_files, extract_zip, wait_for_completion


def serve(args: argparse.Namespace) -> int:
    uvicorn.run("image_to_word.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def convert(args: argparse.Namespace) -> int:
    settings = get_settings()
    client = MineruClient(api_token=settings.mineru_api_token, api_base=settings.mineru_api_base)
    source = Path(args.input).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    out_docx = Path(args.out).expanduser().resolve()
    run_dir = PROJECT_ROOT / "data" / "cli" / f"{int(time.time())}_{source.stem}"
    run_dir.mkdir(parents=True, exist_ok=True)

    options = ConversionOptions(
        language=args.language,
        model_version=args.model_version or settings.mineru_model_version,
        enable_formula=not args.disable_formula,
        enable_table=not args.disable_table,
        is_ocr=not args.text_mode,
        page_ranges=args.page_ranges,
    )
    task = client.submit_file(source, options)
    print(f"submitted batch_id={task.batch_id}")
    result = wait_for_completion(client, task, interval=args.interval, timeout=args.timeout)
    if result.status != "done" or not result.full_zip_url:
        raise RuntimeError(result.message or "MinerU conversion failed")

    zip_path = client.download_zip(result.full_zip_url, run_dir / "mineru_result.zip")
    extract_dir = run_dir / "extract"
    extract_zip(zip_path, extract_dir)
    files = discover_result_files(extract_dir, zip_path)
    if not files.docx:
        raise RuntimeError(f"MinerU result did not contain a DOCX file. Extracted files are in {extract_dir}")

    out_docx.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(files.docx, out_docx)
    print(f"wrote {out_docx}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image-to-word", description="Convert images/PDFs into editable Word documents.")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="start the web UI")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.set_defaults(func=serve)

    convert_parser = subparsers.add_parser("convert", help="convert one local file to DOCX")
    convert_parser.add_argument("input")
    convert_parser.add_argument("--out", required=True)
    convert_parser.add_argument("--language", default="ch")
    convert_parser.add_argument("--model-version", default=None)
    convert_parser.add_argument("--page-ranges", default=None)
    convert_parser.add_argument("--interval", type=float, default=5.0)
    convert_parser.add_argument("--timeout", type=float, default=1200.0)
    convert_parser.add_argument("--disable-formula", action="store_true")
    convert_parser.add_argument("--disable-table", action="store_true")
    convert_parser.add_argument("--text-mode", action="store_true", help="use text parsing mode instead of OCR where MinerU supports it")
    convert_parser.set_defaults(func=convert)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
