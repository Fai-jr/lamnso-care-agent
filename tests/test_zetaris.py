import pytest

from backend.app.config import get_settings
from backend.app.zetaris import ZetarisClient, ZetarisError, _single_statement


class FakeCursor:
    def __init__(self, rows, cols, fail=None):
        self._rows, self.description = rows, ([(c,) for c in cols] if cols else None)
        self.fail, self.executed, self.closed = fail, [], False

    def execute(self, sql):
        if self.fail:
            raise RuntimeError(self.fail)
        self.executed.append(sql)

    def fetchall(self):
        return self._rows

    def close(self):
        self.closed = True


class FakeConn:
    def __init__(self, cursor):
        self._cursor, self.closed = cursor, False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def client(cursor, password="s3cret"):
    return ZetarisClient("jdbc:x", "drv", "/jar", "u", password, connect=lambda *a: FakeConn(cursor))


def test_query_returns_dict_rows_and_closes_cursor():
    cur = FakeCursor([(1, "a"), (2, "b")], ["id", "name"])
    rows = client(cur).query("SELECT id, name FROM t;")
    assert rows == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    assert cur.executed == ["SELECT id, name FROM t"] and cur.closed


def test_statement_without_result_set_returns_empty_list():
    assert client(FakeCursor([], None)).query("CREATE NAMESPACE x") == []


def test_one_statement_per_call():
    with pytest.raises(ZetarisError):
        _single_statement("SELECT 1; SELECT 2")
    assert _single_statement("INSERT INTO t VALUES ('a;b')") == "INSERT INTO t VALUES ('a;b')"


def test_sql_error_is_wrapped():
    with pytest.raises(ZetarisError, match="SQL failed"):
        client(FakeCursor([], ["x"], fail="boom")).query("SELECT 1")


def test_connection_error_never_leaks_the_password():
    def bad(*a):
        raise RuntimeError("login failed for s3cret")

    c = ZetarisClient("jdbc:x", "drv", "/jar", "u", "s3cret", connect=bad)
    with pytest.raises(ZetarisError) as e:
        c.query("SELECT 1")
    assert "s3cret" not in str(e.value) and "s3cret" not in repr(c)


def test_health():
    assert client(FakeCursor([(1,)], ["1"])).health() == "online"
    assert client(FakeCursor([], ["x"], fail="down")).health() == "offline"


def test_from_settings_rejects_placeholders(monkeypatch):
    for k, v in (("ZETARIS_JAR_PATH", "/path/to/x.jar"), ("ZETARIS_USER", "u"), ("ZETARIS_PASSWORD", "p")):
        monkeypatch.setenv(k, v)
    with pytest.raises(ZetarisError, match="ZETARIS_JAR_PATH"):
        ZetarisClient.from_settings(get_settings())


def test_secrets_are_not_in_settings_repr(monkeypatch):
    monkeypatch.setenv("ZETARIS_PASSWORD", "topsecret")
    monkeypatch.setenv("METERLESS_RUNTIME_TOKEN", "tok123")
    r = repr(get_settings())
    assert "topsecret" not in r and "tok123" not in r
