"""Check the AI provider connection, using the same client the app uses.

    python scripts/check_nightshift.py

Reads .env (METERLESS_BASE_URL, METERLESS_RUNTIME_TOKEN, METERLESS_MODEL). Works with a Meterless Runtime
(Nightshift) or, for testing, any OpenAI-compatible endpoint such as NVIDIA's hosted API.
Prints the status, the model that answered and the latency. Never prints the token.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings  # noqa: E402
from backend.app.nightshift import NightshiftClient, NightshiftError, NightshiftUnauthorized  # noqa: E402


def run(client: NightshiftClient) -> int:
    print(f"Endpoint : {client.base_url}")
    print(f"Model    : {client.model}")
    state = client.health()
    print(f"Health   : {state}")
    if state == "unauthorized":
        print("-> The endpoint rejected the key. Check METERLESS_RUNTIME_TOKEN in .env.")
        return 1
    if state == "offline":
        print("-> Could not reach the endpoint. Check METERLESS_BASE_URL and your internet connection.")
        return 1
    try:
        r = client.chat([
            {"role": "system", "content": "Reply in two short, simple sentences."},
            {"role": "user", "content": "Say hello to someone who feels tired today."},
        ])
    except NightshiftUnauthorized:
        print("-> Key rejected on the chat call.")
        return 1
    except NightshiftError as exc:
        print(f"-> Chat failed: {exc}")
        print("   If it says 'empty answer', the model may be spending its tokens on reasoning; tell me.")
        return 1
    print(f"Answered by : {r.model}   ({r.latency_ms} ms)")
    print(f"Reply       : {r.text}")
    return 0


def main() -> int:
    s = get_settings()
    if not s.nightshift_token or s.nightshift_token.startswith("your-"):
        print("Set METERLESS_RUNTIME_TOKEN in .env first (it is empty or still the placeholder).")
        return 1
    return run(NightshiftClient(s.nightshift_base_url, s.nightshift_token, s.nightshift_model,
                                s.app_id, timeout=s.nightshift_timeout,
                                extra_body=s.nightshift_extra_body))


if __name__ == "__main__":
    sys.exit(main())
