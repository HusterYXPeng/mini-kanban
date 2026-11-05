import sqlite3
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Card, Column

EXPECTED_COLUMN_FIELDS = {"id", "title", "position", "created_at", "updated_at"}
EXPECTED_CARD_FIELDS = {
    "id",
    "column_id",
    "title",
    "description",
    "position",
    "created_at",
    "updated_at",
}


def test_get_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startup_creates_tables_and_is_safe_to_repeat(db_path):
    url = f"sqlite:///{db_path}"

    with TestClient(create_app(url)) as client:
        assert client.get("/health").status_code == 200
        assert _table_names(db_path) >= {"columns", "cards"}

    with TestClient(create_app(url)) as client:
        assert client.get("/health").status_code == 200

    assert _columns(db_path, "columns") >= EXPECTED_COLUMN_FIELDS
    assert _columns(db_path, "cards") >= EXPECTED_CARD_FIELDS


def test_rows_store_position_and_utc_timestamps(client, app):
    session = app.state.session_factory()
    try:
        column = Column(title="To Do", position=1)
        session.add(column)
        session.flush()
        card = Card(
            column_id=column.id,
            title="Write health check",
            description=None,
            position=2,
        )
        session.add(card)
        session.commit()

        assert column.position == 1
        assert card.position == 2
        assert card.column_id == column.id
        datetime.strptime(column.created_at, "%Y-%m-%dT%H:%M:%SZ")
        datetime.strptime(card.updated_at, "%Y-%m-%dT%H:%M:%SZ")
        assert column.created_at.endswith("Z")
        assert card.created_at.endswith("Z")
    finally:
        session.close()


def _table_names(db_path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {row[0] for row in rows}


def _columns(db_path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in rows}
