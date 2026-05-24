from __future__ import annotations

import zipfile
from pathlib import Path

from image_to_word.mineru import discover_result_files, extract_zip, safe_filename


def test_safe_filename_keeps_extension() -> None:
    assert safe_filename("../题目 01.png").endswith(".png")
    assert "/" not in safe_filename("../题目 01.png")


def test_extract_zip_skips_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "result.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../bad.txt", "bad")
        zf.writestr("ok/full.md", "# ok")

    out_dir = tmp_path / "extract"
    extract_zip(archive, out_dir)

    assert not (tmp_path / "bad.txt").exists()
    assert (out_dir / "ok" / "full.md").read_text(encoding="utf-8") == "# ok"


def test_discover_result_files_prefers_full_outputs(tmp_path: Path) -> None:
    extract_dir = tmp_path / "extract"
    extract_dir.mkdir()
    (extract_dir / "notes.md").write_text("notes", encoding="utf-8")
    (extract_dir / "full.md").write_text("full", encoding="utf-8")
    (extract_dir / "full.docx").write_bytes(b"docx")
    (extract_dir / "index.html").write_text("<p>ok</p>", encoding="utf-8")

    files = discover_result_files(extract_dir)

    assert files.markdown == extract_dir / "full.md"
    assert files.docx == extract_dir / "full.docx"
    assert files.html == extract_dir / "index.html"
