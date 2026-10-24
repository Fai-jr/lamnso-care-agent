"""Create (or verify) the app's Zetaris datalake, tables and seed data. Safe to run again and again.

    python scripts/setup_zetaris.py               # set up, then show row counts
    python scripts/setup_zetaris.py --selftest    # also check INSERT / SELECT / DELETE on check-ins

Needs the Zetaris stack running (see README) and ZETARIS_* set in .env. No passwords are printed.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import get_settings  # noqa: E402
from backend.app.store import NS, TABLES, ZetarisStore  # noqa: E402
from backend.app.zetaris import ZetarisClient, ZetarisError  # noqa: E402


def ensure_dir(path: str) -> str:
    """A datalake folder may have to exist first: create it inside the driver container (best effort)."""
    compose = Path(os.environ.get("ZETARIS_COMPOSE", "~/zetaris-platform/docker-compose.yml")).expanduser()
    if not compose.exists():
        return "skipped (no compose file found; create the folder yourself if setup fails)"
    try:
        r = subprocess.run(["docker", "compose", "-f", str(compose), "exec", "-T", "driver", "mkdir", "-p", path],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"skipped ({exc.__class__.__name__})"
    return "ok" if r.returncode == 0 else "failed: " + r.stderr.strip()[:200]


def selftest(store: ZetarisStore) -> None:
    key = "f" * 32
    print("\nSelf-test on check-ins (uses a throwaway key):")
    store.add_checkin(key, 3, "other")
    n1 = store.client.query(f"SELECT COUNT(*) AS n FROM {NS}.checkins WHERE user_key = '{key}'")[0]["n"]
    print(f"  insert + count      -> {n1} row(s)")
    try:
        store.forget_checkins(key)
        n2 = store.client.query(f"SELECT COUNT(*) AS n FROM {NS}.checkins WHERE user_key = '{key}'")[0]["n"]
        print(f"  DELETE ... WHERE    -> {n2} row(s) left  ({'supported' if int(n2) == 0 else 'NOT effective'})")
    except ZetarisError as exc:
        print("  DELETE ... WHERE    -> NOT supported:", str(exc)[:300])
        print("  (check-ins cannot be erased on this instance; tell me and I will change the design)")


def main() -> int:
    settings = get_settings()
    try:
        store = ZetarisStore(ZetarisClient.from_settings(settings), settings.zetaris_storage_path)
        report = store.setup(ensure_dir=ensure_dir)
    except ZetarisError as exc:
        print("Setup failed:", str(exc)[:600])
        return 1
    print(f"Datalake : {report['datalake']}  (storage path {settings.zetaris_storage_path})")
    if "directory" in report:
        print(f"Directory: {report['directory']}")
    for table in TABLES:
        print(f"Table    : {table:16} {report['tables'][table]:8} rows={store.count(table)}")
    if report["seeded"]:
        print(f"Seeded   : {report['seeded']} coping ideas")
    if "--selftest" in sys.argv:
        selftest(store)
    store.client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
