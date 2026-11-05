import pytest

from app.models import Column
from tests.support import (
    COLUMN_FIELDS,
    STALE_TIMESTAMP,
    assert_utc_timestamp,
    set_updated_at,
)


def test_list_columns_starts_empty(client):
    response = client.get("/columns")

    assert response.status_code == 200
    assert response.json() == []


def test_column_round_trip(client):
    created = client.post("/columns", json={"title": "To Do"})

    assert created.status_code == 201
    body = created.json()
    assert set(body) == COLUMN_FIELDS
    assert isinstance(body["id"], int)
    assert body["title"] == "To Do"
    assert body["position"] == 0
    assert_utc_timestamp(body["created_at"])
    assert_utc_timestamp(body["updated_at"])

    fetched = client.get(f"/columns/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    listed = client.get("/columns")
    assert listed.status_code == 200
    assert listed.json() == [body]

    patched = client.patch(f"/columns/{body['id']}", json={"title": "Doing"})
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["title"] == "Doing"
    assert patched_body["id"] == body["id"]
    assert patched_body["position"] == 0
    assert patched_body["created_at"] == body["created_at"]

    deleted = client.delete(f"/columns/{body['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    missing = client.get(f"/columns/{body['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Column not found"}
    assert client.get("/columns").json() == []


def test_create_column_requires_title(client):
    missing = client.post("/columns", json={})
    null_title = client.post("/columns", json={"title": None})
    blank = client.post("/columns", json={"title": ""})

    assert missing.status_code == 422
    assert null_title.status_code == 422
    assert blank.status_code == 422
    assert "title" in missing.text
    assert client.get("/columns").json() == []


def test_column_title_length_limits(client):
    accepted = client.post("/columns", json={"title": "t" * 200})
    rejected = client.post("/columns", json={"title": "t" * 201})

    assert accepted.status_code == 201
    assert accepted.json()["title"] == "t" * 200
    assert rejected.status_code == 422
    assert len(client.get("/columns").json()) == 1


def test_omitted_position_appends_columns(client):
    first = client.post("/columns", json={"title": "To Do"})
    second = client.post("/columns", json={"title": "Done"})

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["position"] == 0
    assert second.json()["position"] == 1


def test_null_position_appends_a_column(client):
    response = client.post("/columns", json={"title": "To Do", "position": None})

    assert response.status_code == 201
    assert response.json()["position"] == 0


def test_explicit_column_position_is_stored_and_list_is_ordered(client):
    later = client.post("/columns", json={"title": "Later", "position": 5})
    sooner = client.post("/columns", json={"title": "Sooner", "position": 1})
    tail = client.post("/columns", json={"title": "Tail"})

    assert later.status_code == 201
    assert sooner.status_code == 201
    assert tail.status_code == 201
    assert later.json()["position"] == 5
    assert sooner.json()["position"] == 1
    assert tail.json()["position"] == 6
    listed = client.get("/columns").json()
    assert [column["title"] for column in listed] == ["Sooner", "Later", "Tail"]


@pytest.mark.parametrize("position", [-1, -8])
def test_negative_column_position_is_422(client, position):
    response = client.post("/columns", json={"title": "To Do", "position": position})

    assert response.status_code == 422
    assert "position" in response.text
    assert client.get("/columns").json() == []


def test_create_column_rejects_unknown_fields(client):
    response = client.post("/columns", json={"title": "To Do", "status": "open"})

    assert response.status_code == 422
    assert client.get("/columns").json() == []


def test_missing_column_is_404(client):
    missing = client.get("/columns/999")
    patched = client.patch("/columns/999", json={"title": "Nope"})
    deleted = client.delete("/columns/999")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Column not found"}
    assert patched.status_code == 404
    assert deleted.status_code == 404


def test_non_integer_column_id_is_422(client):
    response = client.get("/columns/not-an-id")

    assert response.status_code == 422


def test_patch_column_updates_timestamp_and_leaves_position(client, app):
    created = client.post("/columns", json={"title": "To Do"}).json()
    set_updated_at(app, Column, created["id"])

    response = client.patch(f"/columns/{created['id']}", json={"title": "Doing"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Doing"
    assert body["position"] == created["position"]
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] != STALE_TIMESTAMP
    assert_utc_timestamp(body["updated_at"])
    assert client.get(f"/columns/{created['id']}").json() == body


def test_empty_column_patch_does_not_write(client, app):
    created = client.post("/columns", json={"title": "To Do"}).json()
    set_updated_at(app, Column, created["id"])

    response = client.patch(f"/columns/{created['id']}", json={})

    assert response.status_code == 200
    assert response.json()["title"] == "To Do"
    assert response.json()["updated_at"] == STALE_TIMESTAMP


def test_patch_column_rejects_null_title(client):
    created = client.post("/columns", json={"title": "To Do"}).json()

    response = client.patch(f"/columns/{created['id']}", json={"title": None})

    assert response.status_code == 422
    assert client.get(f"/columns/{created['id']}").json()["title"] == "To Do"


@pytest.mark.parametrize(
    "payload",
    [
        {"position": 1},
        {"column_id": 1},
        {"status": "done"},
        {"title": "Renamed", "position": 4},
        {"title": "Renamed", "column_id": 9},
        {"title": "Renamed", "status": "archived"},
    ],
)
def test_patch_column_rejects_forbidden_fields(client, payload):
    created = client.post("/columns", json={"title": "To Do"}).json()

    response = client.patch(f"/columns/{created['id']}", json=payload)

    assert response.status_code == 422
    current = client.get(f"/columns/{created['id']}").json()
    assert current["title"] == "To Do"
    assert current["position"] == created["position"]


def test_forbidden_column_patch_does_not_change_updated_at(client, app):
    created = client.post("/columns", json={"title": "To Do"}).json()
    set_updated_at(app, Column, created["id"])

    response = client.patch(
        f"/columns/{created['id']}",
        json={"title": "Doing", "position": 3},
    )

    assert response.status_code == 422
    current = client.get(f"/columns/{created['id']}").json()
    assert current["title"] == "To Do"
    assert current["position"] == 0
    assert current["updated_at"] == STALE_TIMESTAMP


def test_delete_column_does_not_compact_remaining_positions(client):
    first = client.post("/columns", json={"title": "A"}).json()
    second = client.post("/columns", json={"title": "B"}).json()
    third = client.post("/columns", json={"title": "C"}).json()

    deleted = client.delete(f"/columns/{second['id']}")

    assert deleted.status_code == 204
    remaining = client.get("/columns").json()
    assert [(column["title"], column["position"]) for column in remaining] == [
        ("A", first["position"]),
        ("C", third["position"]),
    ]
