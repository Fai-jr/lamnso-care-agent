"""Client for Meterless Nightshift (Meterless Runtime), the app's primary AI provider.

The runtime exposes an OpenAI-compatible API. Contract used here:
  * base URL  http://127.0.0.1:8088/v1 by default (normalised so it never becomes /v1/v1)
  * auth      Authorization: Bearer <token>   (the token is written by the runtime; set NIGHTSHIFT_TOKEN)
  * headers   meterless-app: <stable app id>, meterless-scope: user
  * models    GET /v1/models decides health: 401/403 = unauthorized, 200 = online
  * model ids are routing modes such as meterless/auto; NVIDIA Nemotron is selected by adding the
    NVIDIA key in Nightshift's Providers tab and choosing the mode/model per the Participant Setup Guide.
Which model actually answered is recorded from the response, so traces can show it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


class NightshiftError(RuntimeError):
    """Nightshift could not produce an answer (offline, timeout, bad response)."""


class NightshiftUnauthorized(NightshiftError):
    """401/403: the runtime token is missing or wrong."""


@dataclass
class LLMResult:
    text: str
    model: str            # model reported by the runtime for this answer
    requested_model: str  # routing mode we asked for
    latency_ms: int
    meterless: dict[str, Any] = field(default_factory=dict)  # raw routing info, if the runtime sends it


def normalise_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/models", "/healthz"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def _extract_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):  # array of parts
        return "".join(p.get("text", "") for p in content if isinstance(p, dict)).strip()
    return ""


class NightshiftClient:
    def __init__(self, base_url: str, token: str, model: str, app_id: str,
                 timeout: float = 180.0, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, extra_body: dict[str, Any] | None = None):
        self.base_url = normalise_base_url(base_url)
        self.token = token
        self.model = model
        self.app_id = app_id
        self._sleep = sleep
        self.extra_body = dict(extra_body or {})
        # 180 s: a model load on the runtime can take minutes.
        self._http = httpx.Client(timeout=timeout, transport=transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "meterless-app": self.app_id,
            "meterless-scope": "user",
            "Content-Type": "application/json",
        }

    def health(self) -> str:
        """'online', 'unauthorized' or 'offline'. /v1/models decides (/healthz only proves the process is up)."""
        try:
            r = self._http.get(f"{self.base_url}/models", headers=self._headers(), timeout=5)
        except httpx.HTTPError:
            return "offline"
        if r.status_code in (401, 403):
            return "unauthorized"
        return "online" if r.status_code == 200 else "offline"

    def chat(self, messages: list[dict[str, str]], max_tokens: int = 1024,
             temperature: float = 0.4) -> LLMResult:
        body = {**self.extra_body, "model": self.model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature, "stream": False}
        started = time.monotonic()
        resp = None
        for delay in (2, 4, 8, None):  # 429: retry after 2 s, 4 s, 8 s, then surface
            try:
                resp = self._http.post(f"{self.base_url}/chat/completions",
                                       headers=self._headers(), json=body)
            except httpx.HTTPError as exc:
                raise NightshiftError(f"Nightshift unreachable: {exc.__class__.__name__}") from exc
            if resp.status_code == 429 and delay is not None:
                self._sleep(delay)
                continue
            break
        assert resp is not None
        if resp.status_code in (401, 403):
            raise NightshiftUnauthorized("Nightshift rejected the token (check NIGHTSHIFT_TOKEN)")
        if resp.status_code != 200:
            raise NightshiftError(f"Nightshift returned HTTP {resp.status_code}")
        try:
            data = resp.json()
            text = _extract_text(data["choices"][0]["message"])
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise NightshiftError("Unreadable response from Nightshift") from exc
        if not text:
            raise NightshiftError("Nightshift returned an empty answer")
        return LLMResult(
            text=text,
            model=str(data.get("model") or self.model),
            requested_model=self.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            meterless=data.get("meterless") if isinstance(data.get("meterless"), dict) else {},
        )


class SampleNightshift:
    """Offline stand-in used when SAMPLE_MODE=true. Clearly labelled; never pretends to be a real model."""

    def health(self) -> str:
        return "sample"

    def chat(self, messages, max_tokens: int = 1024, temperature: float = 0.4) -> LLMResult:
        return LLMResult(
            text=("I am sorry you are feeling this way. It sounds like a lot to carry. "
                  "Would you like to tell me more about what has been happening?"),
            model="sample-mode",
            requested_model="sample-mode",
            latency_ms=0,
        )
