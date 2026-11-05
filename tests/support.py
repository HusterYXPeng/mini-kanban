"""Shared assertions for the column and card API tests."""

from datetime import datetime

from sqlalchemy import update

STALE_TIMESTAMP = "2020-01-01T00:00:00Z"

COLUMN_FIELDS = {"id", "title", "position", "created_at", "updated_at"}
CARD_FIELDS = {
    "id",
    "column_id",
    "title",
    "description",
    "position",
    "created_at",
    "updated_at",
}


def assert_utc_timestamp(value: str) -> None:
    datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    assert value.endswith("Z")


def set_updated_at(app, model, row_id: int, stamp: str = STALE_TIMESTAMP) -> None:
    """Write a known timestamp so a later update is visible within one second."""
    session = app.state.session_factory()
    try:
        result = session.execute(
            update(model).where(model.id == row_id).values(updated_at=stamp)
        )
        assert result.rowcount == 1
        session.commit()
    finally:
        session.close()
