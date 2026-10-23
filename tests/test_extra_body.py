import json

import httpx
import pytest

from backend.app.config import _load_dotenv, get_settings
from backend.app.nightshift import NightshiftClient

EXTRA = {"chat_template_kwargs": {"enable_thinking": False}}


def test_extra_body_is_sent_but_core_fields_win():
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    c = NightshiftClient("http://x/v1", "k", "m1", "app", transport=httpx.MockTransport(handler),
                         extra_body={**EXTRA, "model": "SHOULD-NOT-WIN", "stream": True})
    c.chat([{"role": "user", "content": "hi"}])
    assert seen["chat_template_kwargs"] == {"enable_thinking": False}
    assert seen["model"] == "m1" and seen["stream"] is False


def test_extra_body_from_env_and_validation(monkeypatch):
    monkeypatch.delenv("NIGHTSHIFT_EXTRA_BODY", raising=False)
    monkeypatch.setenv("METERLESS_EXTRA_BODY", json.dumps(EXTRA))
    assert get_settings().nightshift_extra_body == EXTRA
    monkeypatch.setenv("METERLESS_EXTRA_BODY", "not json")
    with pytest.raises(ValueError, match="METERLESS_EXTRA_BODY"):
        get_settings()
    monkeypatch.setenv("METERLESS_EXTRA_BODY", "[1,2]")
    with pytest.raises(ValueError, match="JSON object"):
        get_settings()
    monkeypatch.delenv("METERLESS_EXTRA_BODY")
    assert get_settings().nightshift_extra_body == {}


def test_dotenv_line_with_json_value_survives_loading(tmp_path, monkeypatch):
    monkeypatch.delenv("METERLESS_EXTRA_BODY", raising=False)
    env = tmp_path / ".env"
    env.write_text('METERLESS_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}\n')
    _load_dotenv(env)
    assert get_settings().nightshift_extra_body == EXTRA
    monkeypatch.delenv("METERLESS_EXTRA_BODY", raising=False)
