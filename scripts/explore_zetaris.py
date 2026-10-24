"""Probe your Zetaris instance and find a working way to create and use a table.

Zetaris tables live in a DATALAKE (per its SQL guide):
    CREATE DATALAKE <name> OPTIONS (storageType 'Local', storagePath '<path inside the driver container>')
    CREATE TABLE <datalake>.<directory>.<table> (...) USING iceberg
    INSERT INTO <datalake>.<directory>.<table> VALUES (...)      SELECT ... FROM <datalake>.<directory>.<table>

    python scripts/explore_zetaris.py            # read-only discovery
    python scripts/explore_zetaris.py --probe    # also tries candidate storage paths until a test table works

Each statement runs on its own. Errors are expected for some; the output tells us what works. No passwords are printed.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings  # noqa: E402
from backend.app.zetaris import ZetarisClient, ZetarisError  # noqa: E402

READ_ONLY = [
    "SELECT 1",
    "DESCRIBE MASTER DATASOURCE",
    "SHOW DATASOURCE TABLES",
    "DESCRIBE TABLES",
    "SHOW CACHE TABLES",
    "SHOW NAMESPACES OR TABLES IN lightning.metastore",
]

DEFAULT_PATHS = ["/data/lamnso-lakehouse", "/opt/zetaris/lamnso-lakehouse", "/home/zetaris/lamnso-lakehouse",
                 "/tmp/lamnso-lakehouse"]  # /tmp works but does not survive the container being recreated


def candidate_paths() -> list:
    """Mount points of the driver's volumes (from the platform's docker-compose.yml) come first."""
    compose = Path(os.environ.get("ZETARIS_COMPOSE", "~/zetaris-platform/docker-compose.yml")).expanduser()
    found = []
    if compose.exists():
        text = compose.read_text(encoding="utf-8", errors="replace")
        for target in re.findall(r"^\s*-\s*(?:driver-data|customer-data)\s*:\s*(/[^\s:]+)", text, flags=re.M):
            found.append(target.rstrip("/") + "/lamnso-lakehouse")
    return list(dict.fromkeys(found + DEFAULT_PATHS))


def run(client, statements, label_ok="OK") -> bool:
    all_ok = True
    for sql in statements:
        print(f"\n> {sql}")
        try:
            rows = client.query(sql)
        except ZetarisError as exc:
            print("  ERROR:", str(exc)[:450])
            all_ok = False
            continue
        print(f"  {label_ok} ({len(rows)} rows)")
        for row in rows[:25]:
            print("   ", row)
        if len(rows) > 25:
            print(f"    ... {len(rows) - 25} more")
    return all_ok


def attempt(client, sql) -> bool:
    print(f"\n> {sql}")
    try:
        rows = client.query(sql)
    except ZetarisError as exc:
        print("  ERROR:", str(exc)[:450])
        return False
    print(f"  OK ({len(rows)} rows)")
    for row in rows[:10]:
        print("   ", row)
    return True


def probe(client) -> None:
    for i, path in enumerate(candidate_paths()):
        lake = f"lamnso_probe_{i}"
        print(f"\n=== candidate {i + 1}: storagePath '{path}' ===")
        ok = (attempt(client, f"CREATE DATALAKE {lake} OPTIONS (storageType 'Local', storagePath '{path}')")
              and attempt(client, f"CREATE TABLE {lake}.app.healthcheck (id BIGINT, note STRING) USING iceberg"))
        if not ok:
            attempt(client, f"DROP DATALAKE {lake}")   # best effort, so failed probes do not pile up
            continue
        attempt(client, f"INSERT INTO {lake}.app.healthcheck VALUES (1, 'hello')")
        attempt(client, f"SELECT * FROM {lake}.app.healthcheck")
        attempt(client, f"DROP TABLE {lake}.app.healthcheck")
        print(f"\n*** SUCCESS: datalake '{lake}' with storagePath '{path}' can create tables. ***")
        print("    Tell me this path. The probe datalake can stay; the real setup script creates its own.")
        return
    print("\nNo candidate path worked. Paste this whole output and the result of:")
    print("  grep -nE 'volumes|driver-data|customer-data' ~/zetaris-platform/docker-compose.yml")


def main() -> None:
    try:
        client = ZetarisClient.from_settings(get_settings())
    except ZetarisError as exc:
        sys.exit(str(exc))
    try:
        run(client, READ_ONLY)
        if "--probe" in sys.argv:
            probe(client)
    finally:
        client.close()


if __name__ == "__main__":
    main()
