from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    mineru_api_token: str
    mineru_api_base: str
    mineru_model_version: str
    data_dir: Path
    preview_limit: int


def get_settings() -> Settings:
    data_dir = os.getenv("IMAGE_TO_WORD_DATA_DIR", "data/jobs")
    preview_limit = int(os.getenv("IMAGE_TO_WORD_PREVIEW_LIMIT", "200000"))
    return Settings(
        mineru_api_token=os.getenv("MINERU_API_TOKEN", "").strip(),
        mineru_api_base=os.getenv("MINERU_API_BASE", "https://mineru.net/api/v4").strip().rstrip("/"),
        mineru_model_version=os.getenv("MINERU_MODEL_VERSION", "vlm").strip() or "vlm",
        data_dir=(PROJECT_ROOT / data_dir).resolve() if not Path(data_dir).is_absolute() else Path(data_dir),
        preview_limit=preview_limit,
    )
