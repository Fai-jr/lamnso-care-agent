"""Thin client for Zetaris (the app's data layer) over JDBC.

Dialect-agnostic on purpose: it connects, runs ONE statement per call (the platform requires that) and
returns rows as dicts. Table layout and DDL live in a separate module once the instance has been explored.
jaydebeapi/JPype are imported lazily so SAMPLE_MODE and the tests need neither Java nor the driver.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Callable, Optional

_PLACEHOLDER_PREFIXES = ("your-", "/path/to", "<")


class ZetarisError(RuntimeError):
    """Connection, configuration or SQL failure (never includes the password)."""


def _single_statement(sql: str) -> str:
    sql = sql.strip()
    without_literals = re.sub(r"'(?:[^']|'')*'", "''", sql)  # a ';' inside a quoted string is fine
    if ";" in without_literals.rstrip(";"):
        raise ZetarisError("One statement per call: remove the extra ';'.")
    return sql.rstrip(";").strip()


class ZetarisClient:
    def __init__(self, jdbc_url: str, driver_class: str, jar_path: str, user: str, password: str,
                 connect: Optional[Callable[..., Any]] = None):
        self.jdbc_url, self.driver_class, self.jar_path = jdbc_url, driver_class, jar_path
        self.user, self._password = user, password
        self._connect = connect  # injectable for tests
        self._conn = None
        self._lock = threading.RLock()  # one JDBC connection, many request threads

    @classmethod
    def from_settings(cls, settings, connect: Optional[Callable[..., Any]] = None) -> "ZetarisClient":
        for name, value in (("ZETARIS_JAR_PATH", settings.zetaris_jar_path),
                            ("ZETARIS_USER", settings.zetaris_user),
                            ("ZETARIS_PASSWORD", settings.zetaris_password)):
            if not value or value.startswith(_PLACEHOLDER_PREFIXES):
                raise ZetarisError(f"Set {name} in .env first (missing or still a placeholder).")
        if connect is None and not Path(settings.zetaris_jar_path).expanduser().exists():
            raise ZetarisError(f"Driver jar not found: {settings.zetaris_jar_path}")
        return cls(settings.zetaris_jdbc_url, settings.zetaris_driver_class,
                   str(Path(settings.zetaris_jar_path).expanduser()),
                   settings.zetaris_user, settings.zetaris_password, connect=connect)

    def __repr__(self) -> str:  # the password must never appear in logs
        return f"ZetarisClient(url={self.jdbc_url!r}, user={self.user!r})"

    def _ensure(self):
        if self._conn is not None:
            return self._conn
        try:
            connect = self._connect
            if connect is None:
                import jaydebeapi  # lazy: needs Java + the driver jar
                connect = jaydebeapi.connect
            self._conn = connect(self.driver_class, self.jdbc_url, [self.user, self._password], self.jar_path)
        except Exception as exc:
            msg = str(exc).replace(self._password, "***") if self._password else str(exc)
            raise ZetarisError(f"Could not connect to Zetaris: {msg[:400]}") from exc
        return self._conn

    def query(self, sql: str) -> list[dict]:
        """Run one statement. Returns rows as dicts, or [] for statements that return nothing."""
        statement = _single_statement(sql)
        with self._lock:
            return self._run(statement)

    def _run(self, statement: str) -> list[dict]:
        cur = self._ensure().cursor()
        try:
            cur.execute(statement)
            if not cur.description:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except ZetarisError:
            raise
        except Exception as exc:
            raise ZetarisError(f"SQL failed: {str(exc)[:400]}") from exc
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def execute(self, sql: str) -> None:
        self.query(sql)

    def health(self) -> str:
        try:
            return "online" if self.query("SELECT 1") else "offline"
        except ZetarisError:
            return "offline"

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
