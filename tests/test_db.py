from dataclasses import dataclass

from kaoseghis_pacs import db


@dataclass
class _FakeCursor:
    query_timeout_ms: int
    execute_calls: list[tuple[str, tuple | None]]
    fetch_rows: list[dict]

    def __init__(self, query_timeout_ms: int):
        self.query_timeout_ms = query_timeout_ms
        self.execute_calls = []
        self.fetch_rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement: str, params=None):
        if params is None:
            self.execute_calls.append((statement, None))
        else:
            self.execute_calls.append((statement, params))

    def fetchall(self):
        return self.fetch_rows


@dataclass
class _FakeConnection:
    cursor_obj: _FakeCursor
    closed: bool = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    def cursor(self):
        return self.cursor_obj


def test_fetch_active_worklist_rows_executes_read_only_and_parameterized_timeout(monkeypatch):
    cursor = _FakeCursor(query_timeout_ms=5000)
    cursor.fetch_rows = [{'mwl_key': 1}]

    def fake_connect(**kwargs):
        return _FakeConnection(cursor_obj=cursor)

    monkeypatch.setattr(db.psycopg2, 'connect', fake_connect)

    cfg = db.EGhisDbConfig(
        host='127.0.0.1',
        port=5432,
        dbname='postgres',
        user='postgres',
        password='secret',
        connect_timeout=5,
        query_timeout_ms=5000,
    )

    rows = db.fetch_active_worklist_rows(cfg, today_yyyymmdd='20260626')

    assert rows == [{'mwl_key': 1}]
    assert cursor.execute_calls == [
        ('SET default_transaction_read_only = on', None),
        ('SET statement_timeout = %s', (5000,)),
        (db._compose_query(), ('20260626', '20260626')),
    ]
