"""Ask your Zetaris instance what it exposes, so the tables can be written for the real dialect.

    python scripts/explore_zetaris.py                 # read-only: lists namespaces and tables
    python scripts/explore_zetaris.py --try-create    # also tries to create a tiny test table in OUR OWN namespace

Each statement runs on its own (the platform allows one per call). Errors are expected for some of them;
the output tells us which paths exist. No passwords are printed.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings  # noqa: E402
from backend.app.zetaris import ZetarisClient, ZetarisError  # noqa: E402

READ_ONLY = [
    "SELECT 1",
    "SHOW NAMESPACES IN lightning",
    "SHOW NAMESPACES IN lightning.lakehouse",
    "SHOW NAMESPACES IN lightning.lakehouse.iceberg",
    "SHOW NAMESPACES IN lightning.datasource",
    "SHOW NAMESPACES IN lightning.metastore",
    "SHOW TABLES IN lightning",
    "SHOW DATABASES",
]

NS = "lightning.lakehouse.iceberg.lamnso_care"
TRY_CREATE = [
    f"CREATE NAMESPACE IF NOT EXISTS {NS}",
    f"CREATE TABLE {NS}.healthcheck (id INT, note STRING)",
    f"INSERT INTO {NS}.healthcheck VALUES (1, 'hello')",
    f"SELECT * FROM {NS}.healthcheck",
    f"DROP TABLE {NS}.healthcheck",
]


def run(client: ZetarisClient, statements: list, stop_on_error: bool = False) -> None:
    for sql in statements:
        print(f"\n> {sql}")
        try:
            rows = client.query(sql)
        except ZetarisError as exc:
            print("  ERROR:", str(exc)[:300])
            if stop_on_error:
                print("  (stopping: later steps depend on this one)")
                return
            continue
        print(f"  OK ({len(rows)} rows)")
        for row in rows[:25]:
            print("   ", row)
        if len(rows) > 25:
            print(f"    ... {len(rows) - 25} more")


def main() -> None:
    try:
        client = ZetarisClient.from_settings(get_settings())
    except ZetarisError as exc:
        sys.exit(str(exc))
    try:
        run(client, READ_ONLY)
        if "--try-create" in sys.argv:
            print("\n=== trying to create a test table in our own namespace ===")
            run(client, TRY_CREATE, stop_on_error=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
