import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import database.db as db  # noqa: E402
from app import app as flask_app  # noqa: E402

USER_A = ("Alice", "alice@example.com", "passwordA1")
USER_B = ("Bob", "bob@example.com", "passwordB1")

# (date, category, amount, description)
EXPENSES_A = [
    ("2026-01-15", "Food", 100.0, "Jan food"),
    ("2026-02-10", "Transport", 200.0, "Feb bus"),
    ("2026-03-05", "Food", 300.0, "Mar food"),
    ("2026-03-20", "Bills", 500.0, "Mar bills"),
]
EXPENSES_B = [
    ("2026-03-10", "Shopping", 9999.0, "Bob secret purchase"),
]


def _insert_expenses(user_id, rows):
    conn = db.get_db()
    try:
        for d, cat, amt, desc in rows:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, amt, cat, d, desc),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    flask_app.config.update({"TESTING": True, "SECRET_KEY": "test-secret"})
    db.init_db()
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def users(app):
    """Create two users with fixed-date expenses. Returns their ids."""
    db.create_user(*USER_A)
    db.create_user(*USER_B)
    a = db.get_user_by_email(USER_A[1])["id"]
    b = db.get_user_by_email(USER_B[1])["id"]
    _insert_expenses(a, EXPENSES_A)
    _insert_expenses(b, EXPENSES_B)
    return {"a": a, "b": b}


@pytest.fixture
def empty_user(app):
    db.create_user("Empty", "empty@example.com", "passwordE1")
    return db.get_user_by_email("empty@example.com")["id"]


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


@pytest.fixture
def auth_client(client, users):
    login_as(client, users["a"])
    return client
