"""Smoke test: connect to Zetaris over JDBC and run SELECT 1.

Run from the repo root (venv active):   python scripts/check_zetaris.py
Reads the same .env as the app. Needs Java 8+, JayDeBeApi and JPype1.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.app.config  # noqa: E402,F401  (loads .env into os.environ)
import jaydebeapi  # noqa: E402


def need(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v or v.startswith(("your-", "/path/to", "<")):
        sys.exit(f"Set {name} in .env first (it is missing or still a placeholder).")
    return v


jar = Path(need("ZETARIS_JAR_PATH")).expanduser()
if not jar.exists():
    sys.exit(f"Driver jar not found: {jar}")

url = os.environ.get("ZETARIS_JDBC_URL", "jdbc:zetaris:lightning@localhost:10000")
driver = os.environ.get("ZETARIS_DRIVER_CLASS", "com.zetaris.lightning.jdbc.LightningDriver")

try:
    conn = jaydebeapi.connect(driver, url, [need("ZETARIS_USER"), need("ZETARIS_PASSWORD")], str(jar))
except Exception as exc:  # show the real reason, never the password
    msg = str(exc)
    print("Connection failed:", msg[:600])
    if "add-opens" in msg or "InaccessibleObject" in msg:
        print("Hint: this driver may not like very new Java. Try Java 17 (see the chat instructions).")
    elif "uthenticat" in msg or "assword" in msg or "ogin" in msg:
        print("Hint: check ZETARIS_USER / ZETARIS_PASSWORD (use the account that signs in at localhost:3000).")
    sys.exit(1)

try:
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("SELECT 1 ->", cur.fetchall())
finally:
    conn.close()
