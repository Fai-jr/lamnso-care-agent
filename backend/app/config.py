"""Settings, read from environment variables / a local .env file.

Nothing secret lives in the repo: copy .env.example to .env and fill it in.
Settings are read on every call so tests can change the environment freely.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
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


def _first(*names: str, default: str = "") -> str:
    """First non-empty environment variable among names (METERLESS_* is preferred, NIGHTSHIFT_* still works)."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


def _json_object(*names: str) -> dict:
    """Optional JSON object from the first set variable, e.g. extra fields for the model request."""
    raw = _first(*names)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"{names[0]} must be a JSON object, for example "
                         '{"chat_template_kwargs":{"enable_thinking":false}}') from exc
    if not isinstance(value, dict):
        raise ValueError(f"{names[0]} must be a JSON object, not {type(value).__name__}")
    return value


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    sample_mode: bool
    nightshift_base_url: str
    nightshift_token: str = field(repr=False)
    nightshift_model: str
    nightshift_timeout: float
    nightshift_extra_body: dict
    app_id: str
    weights_path: Path
    tokenizer_path: Path
    log_path: Path
    log_content: bool
    resources_path: Path
    zetaris_jdbc_url: str
    zetaris_driver_class: str
    zetaris_jar_path: str
    zetaris_user: str
    zetaris_storage_path: str
    zetaris_password: str = field(repr=False)
    hmem_url: str
    hmem_token: str = field(repr=False)


def get_settings() -> Settings:
    return Settings(
        sample_mode=_bool("SAMPLE_MODE", True),
        nightshift_base_url=_first("METERLESS_BASE_URL", "NIGHTSHIFT_BASE_URL", default="http://127.0.0.1:8088/v1"),
        nightshift_token=_first("METERLESS_RUNTIME_TOKEN", "NIGHTSHIFT_TOKEN"),
        nightshift_model=_first("METERLESS_MODEL", "NIGHTSHIFT_MODEL", default="meterless/auto"),
        nightshift_timeout=float(os.environ.get("NIGHTSHIFT_TIMEOUT", "180")),
        nightshift_extra_body=_json_object("METERLESS_EXTRA_BODY", "NIGHTSHIFT_EXTRA_BODY"),
        app_id=os.environ.get("NIGHTSHIFT_APP_ID", "lamnso-care-agent"),
        weights_path=ROOT / os.environ.get("TRANSLATION_WEIGHTS_PATH", "translation/weights/best_model.pt"),
        tokenizer_path=ROOT / os.environ.get("TRANSLATION_TOKENIZER_PATH", "translation/lamnso_tokenizer.model"),
        log_path=ROOT / os.environ.get("TRACE_LOG_PATH", "logs/trace.jsonl"),
        # Message text is NEVER logged unless this is switched on (demo with synthetic data only).
        log_content=_bool("LOG_CONTENT", False),
        resources_path=ROOT / os.environ.get("CRISIS_RESOURCES_PATH", "sample_data/crisis_resources.json"),
        zetaris_jdbc_url=os.environ.get("ZETARIS_JDBC_URL", "jdbc:zetaris:lightning@localhost:10000"),
        zetaris_driver_class=os.environ.get("ZETARIS_DRIVER_CLASS", "com.zetaris.lightning.jdbc.LightningDriver"),
        zetaris_jar_path=os.environ.get("ZETARIS_JAR_PATH", ""),
        zetaris_user=os.environ.get("ZETARIS_USER", ""),
        zetaris_storage_path=os.environ.get("ZETARIS_STORAGE_PATH", "/home/zetaris/customer-data/shared/lamnso-lakehouse"),
        zetaris_password=os.environ.get("ZETARIS_PASSWORD", ""),
        hmem_url=os.environ.get("HMEM_URL", "http://127.0.0.1:8765"),
        hmem_token=os.environ.get("HMEM_TOKEN", ""),
    )
