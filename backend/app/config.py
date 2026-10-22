"""Settings, read from environment variables / a local .env file.

Nothing secret lives in the repo: copy .env.example to .env and fill it in.
Settings are read on every call so tests can change the environment freely.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    sample_mode: bool
    nightshift_base_url: str
    nightshift_token: str
    nightshift_model: str
    nightshift_timeout: float
    app_id: str
    weights_path: Path
    tokenizer_path: Path
    log_path: Path
    log_content: bool
    resources_path: Path


def get_settings() -> Settings:
    return Settings(
        sample_mode=_bool("SAMPLE_MODE", True),
        nightshift_base_url=os.environ.get("NIGHTSHIFT_BASE_URL", "http://127.0.0.1:8088/v1"),
        nightshift_token=os.environ.get("NIGHTSHIFT_TOKEN", ""),
        nightshift_model=os.environ.get("NIGHTSHIFT_MODEL", "meterless/auto"),
        nightshift_timeout=float(os.environ.get("NIGHTSHIFT_TIMEOUT", "180")),
        app_id=os.environ.get("NIGHTSHIFT_APP_ID", "lamnso-care-agent"),
        weights_path=ROOT / os.environ.get("TRANSLATION_WEIGHTS_PATH", "translation/weights/best_model.pt"),
        tokenizer_path=ROOT / os.environ.get("TRANSLATION_TOKENIZER_PATH", "translation/lamnso_tokenizer.model"),
        log_path=ROOT / os.environ.get("TRACE_LOG_PATH", "logs/trace.jsonl"),
        # Message text is NEVER logged unless this is switched on (demo with synthetic data only).
        log_content=_bool("LOG_CONTENT", False),
        resources_path=ROOT / os.environ.get("CRISIS_RESOURCES_PATH", "sample_data/crisis_resources.json"),
    )
