import sqlite3

import pytest

from app.models import Card
from tests.support import (
    CARD_FIELDS,
    STALE_TIMESTAMP,
    assert_utc_timestamp,
    set_updated_at,
)


def add_column(client, title="To Do", **extra):
    response = client.post("/columns", json={"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def add_card(client, column_id, title="Write tests", **extra):
    response = client.post(
        "/cards",
        json={"title": title, "column_id": column_id, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_list_cards_starts_empty(client):
    response = client.get("/cards")

    assert response.status_code == 200
    assert response.json() == []


def test_card_round_trip(client):
    column = add_column(client)
    created = client.post("/cards", json={"title": "Write tests", "column_id": column["id"]})

    assert created.status_code == 201
    body = created.json()
    assert set(body) == CARD_FIELDS
    assert body["title"] == "Write tests"
    assert body["column_id"] == column["id"]
    assert body["description"] is None
    assert body["position"] == 0
    assert_utc_timestamp(body["created_at"])
    assert_utc_timestamp(body["updated_at"])

    fetched = client.get(f"/cards/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    deleted = client.delete(f"/cards/{body['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    missing = client.get(f"/cards/{body['id']}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Card not found"}


def test_create_card_requires_title_and_column_id(client):
    column = add_column(client)

    missing_title = client.post("/cards", json={"column_id": column["id"]})
    missing_column = client.post("/cards", json={"title": "Write tests"})
    missing_both = client.post("/cards", json={})
    blank_title = client.post(
        "/cards",
        json={"title": "", "column_id": column["id"]},
    )
    null_title = client.post(
        "/cards",
        json={"title": None, "column_id": column["id"]},
    )

    assert missing_title.status_code == 422
    assert missing_column.status_code == 422
    assert missing_both.status_code == 422
    assert blank_title.status_code == 422
    assert null_title.status_code == 422
    assert client.get("/cards").json() == []


def test_create_card_unknown_column_is_404(client):
    response = client.post("/cards", json={"title": "Write tests", "column_id": 999})

    assert response.status_code == 404
    assert response.json() == {"detail": "Column not found"}
    assert client.get("/cards").json() == []


def test_card_column_id_must_be_an_integer(client):
    response = client.post("/cards", json={"title": "Write tests", "column_id": "abc"})

    assert response.status_code == 422
    assert client.get("/cards").json() == []


def test_omitted_card_position_appends_within_its_column(client):
    first_column = add_column(client, "To Do")
    second_column = add_column(client, "Done")

    first = add_card(client, first_column["id"], title="A")
    second = add_card(client, first_column["id"], title="B")
    other = add_card(client, second_column["id"], title="C")
    high = add_card(client, first_column["id"], title="D", position=10)
    tail = add_card(client, first_column["id"], title="E")

    assert first["position"] == 0
    assert second["position"] == 1
    assert other["position"] == 0
    assert high["position"] == 10
    assert tail["position"] == 11


def test_null_card_position_appends(client):
    column = add_column(client)

    response = client.post(
        "/cards",
        json={"title": "Write tests", "column_id": column["id"], "position": None},
    )

    assert response.status_code == 201
    assert response.json()["position"] == 0


@pytest.mark.parametrize("position", [-1, -4])
def test_negative_card_position_is_422(client, position):
    column = add_column(client)

    response = client.post(
        "/cards",
        json={"title": "Write tests", "column_id": column["id"], "position": position},
    )

    assert response.status_code == 422
    assert "position" in response.text
    assert client.get("/cards").json() == []


def test_description_max_length_is_1000(client):
    column = add_column(client)
    ok = client.post(
        "/cards",
        json={
            "title": "A",
            "column_id": column["id"],
            "description": "x" * 1000,
        },
    )
    too_long = client.post(
        "/cards",
        json={
            "title": "B",
            "column_id": column["id"],
            "description": "x" * 1001,
        },
    )

    assert ok.status_code == 201
    assert ok.json()["description"] == "x" * 1000
    assert too_long.status_code == 422
    listed = client.get("/cards", params={"column_id": column["id"]}).json()
    assert [card["title"] for card in listed] == ["A"]

    patched = client.patch(f"/cards/{ok.json()['id']}", json={"description": "y" * 1001})
    assert patched.status_code == 422
    assert client.get(f"/cards/{ok.json()['id']}").json()["description"] == "x" * 1000


def test_patch_clears_description(client):
    column = add_column(client)
    card = add_card(client, column["id"], description="Notes")

    response = client.patch(f"/cards/{card['id']}", json={"description": None})

    assert response.status_code == 200
    assert response.json()["description"] is None
    assert response.json()["title"] == card["title"]


def test_list_cards_by_column(client):
    first = add_column(client, "To Do")
    second = add_column(client, "Done")
    kept = add_card(client, first["id"], title="Stay", position=1)
    earlier = add_card(client, first["id"], title="Earlier", position=0)
    other = add_card(client, second["id"], title="Elsewhere")
    empty = add_column(client, "Empty")

    by_query = client.get("/cards", params={"column_id": first["id"]})
    by_path = client.get(f"/columns/{first['id']}/cards")

    assert by_query.status_code == 200
    assert by_path.status_code == 200
    assert [card["id"] for card in by_query.json()] == [earlier["id"], kept["id"]]
    assert by_path.json() == by_query.json()
    assert other["id"] not in {card["id"] for card in by_query.json()}
    assert client.get(f"/columns/{empty['id']}/cards").json() == []
    assert client.get("/cards", params={"column_id": empty["id"]}).json() == []

    missing = client.get("/cards", params={"column_id": 9999})
    missing_path = client.get("/columns/9999/cards")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Column not found"}
    assert missing_path.status_code == 404
    assert missing_path.json() == {"detail": "Column not found"}


def test_list_cards_follows_column_order(client):
    later = add_column(client, "Later", position=2)
    sooner = add_column(client, "Sooner", position=0)
    card_later = add_card(client, later["id"], title="Second", position=0)
    card_sooner_high = add_card(client, sooner["id"], title="First-b", position=3)
    card_sooner_low = add_card(client, sooner["id"], title="First-a", position=1)

    listed = client.get("/cards")

    assert listed.status_code == 200
    assert [card["id"] for card in listed.json()] == [
        card_sooner_low["id"],
        card_sooner_high["id"],
        card_later["id"],
    ]


def test_patch_card_title_and_description(client, app):
    column = add_column(client)
    created = add_card(client, column["id"], description="Notes")
    set_updated_at(app, Card, created["id"])

    title_only = client.patch(f"/cards/{created['id']}", json={"title": "Retitled"})
    assert title_only.status_code == 200
    assert title_only.json()["title"] == "Retitled"
    assert title_only.json()["description"] == "Notes"
    assert title_only.json()["column_id"] == column["id"]
    assert title_only.json()["position"] == created["position"]
    assert title_only.json()["created_at"] == created["created_at"]
    assert title_only.json()["updated_at"] != STALE_TIMESTAMP
    assert_utc_timestamp(title_only.json()["updated_at"])

    set_updated_at(app, Card, created["id"])
    description_only = client.patch(
        f"/cards/{created['id']}",
        json={"description": "More notes"},
    )
    assert description_only.status_code == 200
    assert description_only.json()["title"] == "Retitled"
    assert description_only.json()["description"] == "More notes"
    assert description_only.json()["updated_at"] != STALE_TIMESTAMP

    both = client.patch(
        f"/cards/{created['id']}",
        json={"title": "Final", "description": "Done"},
    )
    assert both.status_code == 200
    assert both.json()["title"] == "Final"
    assert both.json()["description"] == "Done"
    assert client.get(f"/cards/{created['id']}").json() == both.json()


def test_empty_card_patch_does_not_write(client, app):
    column = add_column(client)
    created = add_card(client, column["id"])
    set_updated_at(app, Card, created["id"])

    response = client.patch(f"/cards/{created['id']}", json={})

    assert response.status_code == 200
    assert response.json()["updated_at"] == STALE_TIMESTAMP
    assert response.json()["title"] == created["title"]


@pytest.mark.parametrize(
    "payload",
    [
        {"position": 1},
        {"column_id": 1},
        {"status": "done"},
        {"title": "Renamed", "position": 3},
        {"description": "Moved", "column_id": 8},
        {"title": "Renamed", "status": "archived"},
    ],
)
def test_patch_card_rejects_forbidden_fields(client, payload):
    column = add_column(client)
    created = add_card(client, column["id"], description="Notes")

    response = client.patch(f"/cards/{created['id']}", json=payload)

    assert response.status_code == 422
    current = client.get(f"/cards/{created['id']}").json()
    assert current["title"] == created["title"]
    assert current["description"] == "Notes"
    assert current["column_id"] == column["id"]
    assert current["position"] == created["position"]


def test_forbidden_card_patch_does_not_move_or_retitle(client, app):
    source = add_column(client, "Source")
    target = add_column(client, "Target")
    created = add_card(client, source["id"], description="Notes")
    set_updated_at(app, Card, created["id"])

    response = client.patch(
        f"/cards/{created['id']}",
        json={"title": "Moved", "column_id": target["id"], "position": 4, "status": "done"},
    )

    assert response.status_code == 422
    current = client.get(f"/cards/{created['id']}").json()
    assert current["title"] == created["title"]
    assert current["description"] == "Notes"
    assert current["column_id"] == source["id"]
    assert current["position"] == created["position"]
    assert current["updated_at"] == STALE_TIMESTAMP
    assert client.get(f"/columns/{target['id']}/cards").json() == []


def test_patch_card_rejects_null_title(client):
    column = add_column(client)
    created = add_card(client, column["id"])

    response = client.patch(f"/cards/{created['id']}", json={"title": None})

    assert response.status_code == 422
    assert client.get(f"/cards/{created['id']}").json()["title"] == created["title"]


def test_missing_card_updates_and_deletes_are_404(client):
    patched = client.patch("/cards/999", json={"title": "Nope"})
    deleted = client.delete("/cards/999")

    assert patched.status_code == 404
    assert patched.json() == {"detail": "Card not found"}
    assert deleted.status_code == 404
    assert deleted.json() == {"detail": "Card not found"}


def test_delete_card_compacts_positions_in_that_column(client):
    column = add_column(client)
    first = add_card(client, column["id"], title="A")
    middle = add_card(client, column["id"], title="B")
    last = add_card(client, column["id"], title="C")

    deleted = client.delete(f"/cards/{middle['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/cards/{middle['id']}").status_code == 404
    remaining = client.get("/cards", params={"column_id": column["id"]}).json()
    assert [(card["title"], card["position"]) for card in remaining] == [("A", 0), ("C", 1)]
    appended = add_card(client, column["id"], title="D")
    assert appended["position"] == 2
    assert client.get(f"/cards/{first['id']}").json()["position"] == 0
    assert client.get(f"/cards/{last['id']}").json()["position"] == 1

    assert client.delete(f"/cards/{first['id']}").status_code == 204
    after_second_delete = client.get(f"/columns/{column['id']}/cards").json()
    assert [(card["title"], card["position"]) for card in after_second_delete] == [
        ("C", 0),
        ("D", 1),
    ]


def test_delete_card_compacts_gaps_and_ties(client):
    column = add_column(client)
    add_card(client, column["id"], title="Low", position=1)
    add_card(client, column["id"], title="HighA", position=5)
    add_card(client, column["id"], title="HighB", position=5)
    extra = add_card(client, column["id"], title="Extra", position=9)

    assert client.delete(f"/cards/{extra['id']}").status_code == 204

    remaining = client.get(f"/columns/{column['id']}/cards").json()
    assert [(card["title"], card["position"]) for card in remaining] == [
        ("Low", 0),
        ("HighA", 1),
        ("HighB", 2),
    ]


def test_delete_only_card_leaves_the_column_empty(client):
    column = add_column(client)
    card = add_card(client, column["id"])

    assert client.delete(f"/cards/{card['id']}").status_code == 204
    assert client.get(f"/columns/{column['id']}/cards").json() == []
    assert client.get(f"/columns/{column['id']}").status_code == 200


def test_card_delete_does_not_compact_another_column(client):
    source = add_column(client, "Source")
    other = add_column(client, "Other")
    victim = add_card(client, source["id"], title="Victim", position=0)
    add_card(client, source["id"], title="Sibling", position=1)
    add_card(client, other["id"], title="Left", position=0)
    add_card(client, other["id"], title="Right", position=3)

    assert client.delete(f"/cards/{victim['id']}").status_code == 204

    source_cards = client.get(f"/columns/{source['id']}/cards").json()
    other_cards = client.get(f"/columns/{other['id']}/cards").json()
    assert [(card["title"], card["position"]) for card in source_cards] == [("Sibling", 0)]
    assert [(card["title"], card["position"]) for card in other_cards] == [
        ("Left", 0),
        ("Right", 3),
    ]


def test_delete_card_and_compact_share_a_transaction(client, monkeypatch):
    column = add_column(client)
    first = add_card(client, column["id"], title="Keep")
    second = add_card(client, column["id"], title="Stay")

    def fail(*_args, **_kwargs):
        raise RuntimeError("compact failed")

    monkeypatch.setattr("app.ordering.compact_card_positions", fail)

    with pytest.raises(RuntimeError, match="compact failed"):
        client.delete(f"/cards/{second['id']}")

    listed = client.get("/cards", params={"column_id": column["id"]}).json()
    assert [(card["id"], card["position"]) for card in listed] == [
        (first["id"], 0),
        (second["id"], 1),
    ]


def test_delete_column_cascades_its_cards(client, db_path):
    doomed = add_column(client, "Doomed")
    kept = add_column(client, "Kept")
    gone_cards = [
        add_card(client, doomed["id"], title="One"),
        add_card(client, doomed["id"], title="Two", description="details"),
    ]
    survivor = add_card(client, kept["id"], title="Stay", position=4)

    response = client.delete(f"/columns/{doomed['id']}")

    assert response.status_code == 204
    assert client.get(f"/columns/{doomed['id']}").status_code == 404
    for card in gone_cards:
        fetched = client.get(f"/cards/{card['id']}")
        assert fetched.status_code == 404
        assert fetched.json() == {"detail": "Card not found"}
    assert client.get(f"/cards/{survivor['id']}").json()["position"] == 4
    assert [card["id"] for card in client.get("/cards").json()] == [survivor["id"]]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM cards WHERE column_id = ?",
            (doomed["id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == 0
