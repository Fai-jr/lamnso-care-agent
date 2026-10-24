"""End-to-end against the REAL H-MEM Node service. Skipped unless its dependencies are installed:
    npm --prefix engines/hmem install
"""
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from backend.app.hmem_client import HmemClient, HmemPolicyError, user_key

ENGINE = Path(__file__).resolve().parents[1] / "engines" / "hmem"
pytestmark = pytest.mark.skipif(
    not (shutil.which("node") and (ENGINE / "node_modules" / ".bin" / "tsx").exists()),
    reason="H-MEM service dependencies not installed (npm --prefix engines/hmem install)")


@pytest.fixture(scope="module")
def service(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    data = tmp_path_factory.mktemp("hmem")
    env = {**os.environ, "HMEM_PORT": str(port), "HMEM_DATA_DIR": str(data)}
    proc = subprocess.Popen(["node", "--import", "tsx", "server.ts"], cwd=ENGINE, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if httpx.get(base + "/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    else:
        proc.kill()
        pytest.fail("H-MEM service did not start")
    yield base, data
    proc.terminate()
    proc.wait(timeout=10)


def test_remember_recall_policy_and_forget_over_real_http(service):
    base, data = service
    client = HmemClient(base)
    key = user_key("integration-user")
    assert client.health() == "online"
    client.remember(key, "Evening walks help with feeling anxious before bed")
    notes = client.recall(key, "I feel anxious at night")
    assert [n.content for n in notes] == ["Evening walks help with feeling anxious before bed"]
    assert client.recall(user_key("someone-else"), "I feel anxious at night") == []   # isolation
    with pytest.raises(HmemPolicyError) as e:
        client.remember(key, "Phone her on +237 612 345 678 today")
    assert e.value.code == "pii_suspected"
    assert client.forget(key) == 1
    assert client.recall(key, "anxious at night") == []
    assert "anxious" not in (data / "state.json").read_text() + (data / "ledger.jsonl").read_text()


def test_client_reports_offline_when_the_service_is_not_there():
    assert HmemClient("http://127.0.0.1:9", timeout=0.5).health() == "offline"
