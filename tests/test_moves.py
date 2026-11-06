import pytest

from app import ordering
from app.models import Card, Column
from tests.support import STALE_TIMESTAMP, assert_utc_timestamp, set_updated_at


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


def cards_in(client, column_id):
    response = client.get(f"/columns/{column_id}/cards")
    assert response.status_code == 200, response.text
    return [(card["title"], card["position"]) for card in response.json()]


def column_order(client):
    response = client.get("/columns")
    assert response.status_code == 200, response.text
    return [(column["title"], column["position"]) for column in response.json()]


def test_move_card_within_column_reorders_and_compacts(client):
    column = add_column(client, "To Do")
    other = add_column(client, "Elsewhere")
    first = add_card(client, column["id"], title="A")
    second = add_card(client, column["id"], title="B")
    third = add_card(client, column["id"], title="C")
    fourth = add_card(client, column["id"], title="D")
    add_card(client, other["id"], title="Gap", position=4)
    add_card(client, other["id"], title="Tail", position=9)

    down_one = client.post(
        f"/cards/{first['id']}/move",
        json={"column_id": column["id"], "position": 1},
    )
    assert down_one.status_code == 200
    assert down_one.json()["column_id"] == column["id"]
    assert down_one.json()["position"] == 1
    assert down_one.json()["title"] == "A"
    assert client.get(f"/cards/{first['id']}").json() == down_one.json()
    assert cards_in(client, column["id"]) == [("B", 0), ("A", 1), ("C", 2), ("D", 3)]

    to_front = client.post(
        f"/cards/{fourth['id']}/move",
        json={"column_id": column["id"], "position": 0},
    )
    assert to_front.status_code == 200
    assert to_front.json()["position"] == 0
    assert cards_in(client, column["id"]) == [("D", 0), ("B", 1), ("A", 2), ("C", 3)]

    to_end = client.post(
        f"/cards/{first['id']}/move",
        json={"column_id": column["id"], "position": 3},
    )
    assert to_end.status_code == 200
    assert to_end.json()["position"] == 3
    assert cards_in(client, column["id"]) == [("D", 0), ("B", 1), ("C", 2), ("A", 3)]

    middle = client.post(
        f"/cards/{second['id']}/move",
        json={"column_id": column["id"], "position": 2},
    )
    assert middle.status_code == 200
    assert middle.json()["position"] == 2
    assert cards_in(client, column["id"]) == [("D", 0), ("C", 1), ("B", 2), ("A", 3)]
    assert client.get(f"/cards/{third['id']}").json()["position"] == 1
    assert cards_in(client, other["id"]) == [("Gap", 4), ("Tail", 9)]

    appended = add_card(client, column["id"], title="E")
    assert appended["position"] == 4


def test_move_card_across_columns_compacts_both(client):
    source = add_column(client, "Source")
    target = add_column(client, "Target")
    other = add_column(client, "Other")
    kept = add_card(client, source["id"], title="A", description="keep")
    moving = add_card(client, source["id"], title="B")
    tail = add_card(client, source["id"], title="C")
    left = add_card(client, target["id"], title="X")
    right = add_card(client, target["id"], title="Y")
    add_card(client, other["id"], title="Gap", position=2)
    add_card(client, other["id"], title="Far", position=6)

    to_middle = client.post(
        f"/cards/{moving['id']}/move",
        json={"column_id": target["id"], "position": 1},
    )
    assert to_middle.status_code == 200
    body = to_middle.json()
    assert body["column_id"] == target["id"]
    assert body["position"] == 1
    assert body["title"] == "B"
    assert body["description"] is None
    assert body["created_at"] == moving["created_at"]
    assert client.get(f"/cards/{moving['id']}").json() == body
    assert cards_in(client, source["id"]) == [("A", 0), ("C", 1)]
    assert cards_in(client, target["id"]) == [("X", 0), ("B", 1), ("Y", 2)]
    assert cards_in(client, other["id"]) == [("Gap", 2), ("Far", 6)]

    to_front = client.post(
        f"/cards/{tail['id']}/move",
        json={"column_id": target["id"], "position": 0},
    )
    assert to_front.status_code == 200
    assert cards_in(client, source["id"]) == [("A", 0)]
    assert cards_in(client, target["id"]) == [("C", 0), ("X", 1), ("B", 2), ("Y", 3)]

    back = client.post(
        f"/cards/{left['id']}/move",
        json={"column_id": source["id"], "position": 1},
    )
    assert back.status_code == 200
    assert cards_in(client, source["id"]) == [("A", 0), ("X", 1)]
    assert cards_in(client, target["id"]) == [("C", 0), ("B", 1), ("Y", 2)]

    onto_empty_source = client.post(
        f"/cards/{kept['id']}/move",
        json={"column_id": target["id"], "position": 5},
    )
    assert onto_empty_source.status_code == 200
    assert cards_in(client, source["id"]) == [("X", 0)]
    assert cards_in(client, target["id"]) == [("C", 0), ("B", 1), ("Y", 2), ("A", 3)]

    drain = client.post(
        f"/cards/{left['id']}/move",
        json={"column_id": target["id"], "position": 0},
    )
    assert drain.status_code == 200
    assert client.get(f"/columns/{source['id']}/cards").json() == []
    assert cards_in(client, target["id"]) == [
        ("X", 0),
        ("C", 1),
        ("B", 2),
        ("Y", 3),
        ("A", 4),
    ]
    assert client.get(f"/cards/{kept['id']}").json()["description"] == "keep"
    assert cards_in(client, other["id"]) == [("Gap", 2), ("Far", 6)]
    listed = client.get("/cards").json()
    assert [card["title"] for card in listed] == ["X", "C", "B", "Y", "A", "Gap", "Far"]


def test_move_card_compacts_gaps_and_keeps_unmoved_order(client):
    column = add_column(client)
    low = add_card(client, column["id"], title="Low", position=1)
    high_a = add_card(client, column["id"], title="HighA", position=5)
    high_b = add_card(client, column["id"], title="HighB", position=5)

    moved = client.post(
        f"/cards/{high_b['id']}/move",
        json={"column_id": column["id"], "position": 0},
    )

    assert moved.status_code == 200
    assert cards_in(client, column["id"]) == [("HighB", 0), ("Low", 1), ("HighA", 2)]
    assert client.get(f"/cards/{low['id']}").json()["position"] == 1
    assert client.get(f"/cards/{high_a['id']}").json()["position"] == 2

    gapped = add_column(client, "Gapped")
    add_card(client, gapped["id"], title="First", position=0)
    add_card(client, gapped["id"], title="Second", position=10)
    incoming = add_card(client, column["id"], title="Incoming")

    appended = client.post(
        f"/cards/{incoming['id']}/move",
        json={"column_id": gapped["id"], "position": 5},
    )

    assert appended.status_code == 200
    assert appended.json()["position"] == 2
    assert cards_in(client, gapped["id"]) == [("First", 0), ("Second", 1), ("Incoming", 2)]


def test_move_column_reorders_and_compacts_the_board(client):
    first = add_column(client, "A")
    second = add_column(client, "B")
    third = add_column(client, "C")
    fourth = add_column(client, "D")
    kept_card = add_card(client, second["id"], title="Stay", position=4)
    add_card(client, second["id"], title="Later", position=8)

    to_front = client.post(f"/columns/{third['id']}/move", json={"position": 0})
    assert to_front.status_code == 200
    assert to_front.json()["title"] == "C"
    assert to_front.json()["position"] == 0
    assert to_front.json()["created_at"] == third["created_at"]
    assert client.get(f"/columns/{third['id']}").json() == to_front.json()
    assert column_order(client) == [("C", 0), ("A", 1), ("B", 2), ("D", 3)]

    to_end = client.post(f"/columns/{first['id']}/move", json={"position": 3})
    assert to_end.status_code == 200
    assert to_end.json()["position"] == 3
    assert column_order(client) == [("C", 0), ("B", 1), ("D", 2), ("A", 3)]

    middle = client.post(f"/columns/{second['id']}/move", json={"position": 2})
    assert middle.status_code == 200
    assert column_order(client) == [("C", 0), ("D", 1), ("B", 2), ("A", 3)]
    assert cards_in(client, second["id"]) == [("Stay", 4), ("Later", 8)]
    assert client.get(f"/cards/{kept_card['id']}").json()["column_id"] == second["id"]

    tail = add_column(client, "E")
    assert tail["position"] == 4
    assert [card["title"] for card in client.get("/cards").json()] == ["Stay", "Later"]


def test_move_column_compacts_gaps_without_rewriting_cards(client):
    first = add_column(client, "A", position=0)
    second = add_column(client, "B", position=10)
    third = add_column(client, "C", position=30)
    add_card(client, first["id"], title="In A", position=2)
    add_card(client, third["id"], title="In C", position=7)

    moved = client.post(f"/columns/{first['id']}/move", json={"position": 5})

    assert moved.status_code == 200
    assert moved.json()["position"] == 2
    assert column_order(client) == [("B", 0), ("C", 1), ("A", 2)]
    assert cards_in(client, first["id"]) == [("In A", 2)]
    assert cards_in(client, third["id"]) == [("In C", 7)]
    assert [card["title"] for card in client.get("/cards").json()] == ["In C", "In A"]
    assert client.get(f"/columns/{second['id']}").json()["position"] == 0


def test_board_list_follows_card_and_column_moves(client):
    sooner = add_column(client, "Sooner", position=0)
    later = add_column(client, "Later", position=1)
    add_card(client, sooner["id"], title="A")
    moving = add_card(client, sooner["id"], title="B")
    add_card(client, later["id"], title="C")

    card_move = client.post(
        f"/cards/{moving['id']}/move",
        json={"column_id": later["id"], "position": 0},
    )
    assert card_move.status_code == 200
    assert [card["title"] for card in client.get("/cards").json()] == ["A", "B", "C"]
    assert cards_in(client, sooner["id"]) == [("A", 0)]
    assert cards_in(client, later["id"]) == [("B", 0), ("C", 1)]

    column_move = client.post(f"/columns/{later['id']}/move", json={"position": 0})
    assert column_move.status_code == 200
    assert column_order(client) == [("Later", 0), ("Sooner", 1)]
    assert [card["title"] for card in client.get("/cards").json()] == ["B", "C", "A"]
    assert client.get(f"/cards/{moving['id']}").json()["position"] == 0


def test_card_move_refreshes_the_moved_card_timestamp(client, app):
    source = add_column(client, "Source")
    target = add_column(client, "Target")
    card = add_card(client, source["id"], title="Move me", description="notes")
    neighbor = add_card(client, target["id"], title="Stay")
    set_updated_at(app, Card, card["id"])
    set_updated_at(app, Column, target["id"])

    response = client.post(
        f"/cards/{card['id']}/move",
        json={"column_id": target["id"], "position": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated_at"] != STALE_TIMESTAMP
    assert_utc_timestamp(body["updated_at"])
    assert body["created_at"] == card["created_at"]
    assert body["description"] == "notes"
    assert body["position"] == 0
    assert client.get(f"/cards/{neighbor['id']}").json()["position"] == 1
    assert client.get(f"/columns/{target['id']}").json()["updated_at"] == STALE_TIMESTAMP
    assert client.get(f"/columns/{source['id']}").json()["updated_at"] == source["updated_at"]


def test_column_move_refreshes_the_moved_column_timestamp(client, app):
    first = add_column(client, "A")
    second = add_column(client, "B")
    card = add_card(client, second["id"], title="Stay", position=3)
    set_updated_at(app, Column, second["id"])
    set_updated_at(app, Card, card["id"])

    response = client.post(f"/columns/{second['id']}/move", json={"position": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["position"] == 0
    assert body["updated_at"] != STALE_TIMESTAMP
    assert_utc_timestamp(body["updated_at"])
    assert body["created_at"] == second["created_at"]
    assert client.get(f"/cards/{card['id']}").json()["updated_at"] == STALE_TIMESTAMP
    assert client.get(f"/cards/{card['id']}").json()["position"] == 3
    assert client.get(f"/columns/{first['id']}").json()["position"] == 1


@pytest.mark.parametrize("position", [-1, -4])
def test_negative_card_move_position_is_422(client, app, position):
    column = add_column(client)
    card = add_card(client, column["id"], title="Stay")
    set_updated_at(app, Card, card["id"])

    response = client.post(
        f"/cards/{card['id']}/move",
        json={"column_id": column["id"], "position": position},
    )

    assert response.status_code == 422
    assert "position" in response.text
    current = client.get(f"/cards/{card['id']}").json()
    assert current["position"] == 0
    assert current["column_id"] == column["id"]
    assert current["updated_at"] == STALE_TIMESTAMP


@pytest.mark.parametrize("position", [-1, -8])
def test_negative_column_move_position_is_422(client, app, position):
    column = add_column(client, "To Do")
    other = add_column(client, "Done")
    set_updated_at(app, Column, column["id"])

    response = client.post(f"/columns/{column['id']}/move", json={"position": position})

    assert response.status_code == 422
    assert "position" in response.text
    assert column_order(client) == [("To Do", 0), ("Done", other["position"])]
    assert client.get(f"/columns/{column['id']}").json()["updated_at"] == STALE_TIMESTAMP


def test_move_card_rejects_invalid_bodies(client):
    column = add_column(client)
    other = add_column(client, "Other")
    card = add_card(client, column["id"], title="Stay", description="Notes")
    add_card(client, other["id"], title="Already", position=4)
    payloads = [
        {},
        {"position": 0},
        {"column_id": other["id"]},
        {"column_id": other["id"], "position": None},
        {"column_id": "nope", "position": 0},
        {"column_id": other["id"], "position": 1.5},
        {"column_id": other["id"], "position": 0, "title": "Moved"},
        {"column_id": other["id"], "position": 0, "status": "done"},
        {"column_id": other["id"], "position": 0, "description": "x"},
    ]

    for payload in payloads:
        response = client.post(f"/cards/{card['id']}/move", json=payload)
        assert response.status_code == 422, payload

    current = client.get(f"/cards/{card['id']}").json()
    assert current["title"] == "Stay"
    assert current["description"] == "Notes"
    assert current["column_id"] == column["id"]
    assert current["position"] == 0
    assert cards_in(client, other["id"]) == [("Already", 4)]


def test_move_column_rejects_invalid_bodies(client):
    column = add_column(client, "To Do")
    payloads = [
        {},
        {"position": None},
        {"position": 1.5},
        {"title": "Doing"},
        {"position": 0, "title": "Doing"},
        {"position": 0, "column_id": 1},
        {"position": 0, "status": "done"},
    ]

    for payload in payloads:
        response = client.post(f"/columns/{column['id']}/move", json=payload)
        assert response.status_code == 422, payload

    current = client.get(f"/columns/{column['id']}").json()
    assert current["title"] == "To Do"
    assert current["position"] == 0


def test_move_missing_ids_are_404(client, app):
    column = add_column(client)
    card = add_card(client, column["id"], title="Stay")
    set_updated_at(app, Card, card["id"])

    missing_card = client.post(
        "/cards/999/move",
        json={"column_id": column["id"], "position": 0},
    )
    missing_column = client.post(
        f"/cards/{card['id']}/move",
        json={"column_id": 9999, "position": 0},
    )
    missing_board_column = client.post("/columns/999/move", json={"position": 0})

    assert missing_card.status_code == 404
    assert missing_card.json() == {"detail": "Card not found"}
    assert missing_column.status_code == 404
    assert missing_column.json() == {"detail": "Column not found"}
    assert missing_board_column.status_code == 404
    assert missing_board_column.json() == {"detail": "Column not found"}
    current = client.get(f"/cards/{card['id']}").json()
    assert current["column_id"] == column["id"]
    assert current["position"] == 0
    assert current["title"] == "Stay"
    assert current["updated_at"] == STALE_TIMESTAMP
    assert client.get(f"/columns/{column['id']}/cards").json()[0]["id"] == card["id"]


def test_non_integer_move_ids_are_422(client):
    card = client.post("/cards/nope/move", json={"column_id": 1, "position": 0})
    column = client.post("/columns/nope/move", json={"position": 0})

    assert card.status_code == 422
    assert column.status_code == 422


def test_patch_still_rejects_position_and_column_id(client):
    source = add_column(client, "Source")
    target = add_column(client, "Target")
    card = add_card(client, source["id"], description="Notes")

    card_patch = client.patch(
        f"/cards/{card['id']}",
        json={"title": "Moved", "column_id": target["id"], "position": 0},
    )
    column_patch = client.patch(
        f"/columns/{source['id']}",
        json={"title": "Renamed", "position": 1},
    )

    assert card_patch.status_code == 422
    assert column_patch.status_code == 422
    current = client.get(f"/cards/{card['id']}").json()
    assert current["title"] == card["title"]
    assert current["description"] == "Notes"
    assert current["column_id"] == source["id"]
    assert current["position"] == card["position"]
    assert client.get(f"/columns/{target['id']}/cards").json() == []
    assert client.get(f"/columns/{source['id']}").json()["title"] == "Source"
    assert client.get(f"/columns/{source['id']}").json()["position"] == source["position"]

    moved = client.post(
        f"/cards/{card['id']}/move",
        json={"column_id": target["id"], "position": 0},
    )
    assert moved.status_code == 200
    assert moved.json()["column_id"] == target["id"]
    assert moved.json()["position"] == 0
    assert moved.json()["title"] == card["title"]


def test_failed_card_move_leaves_both_columns_unchanged(client, monkeypatch):
    source = add_column(client, "Source")
    target = add_column(client, "Target")
    untouched = add_column(client, "Untouched")
    first = add_card(client, source["id"], title="A", position=0)
    add_card(client, source["id"], title="B", position=3)
    add_card(client, target["id"], title="X", position=2)
    add_card(client, target["id"], title="Y", position=7)
    add_card(client, untouched["id"], title="Z", position=4)

    real_compact = ordering.compact_card_positions
    calls = {"n": 0}

    def fail_on_second(session, column_id):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("compact failed")
        return real_compact(session, column_id)

    monkeypatch.setattr("app.ordering.compact_card_positions", fail_on_second)

    with pytest.raises(RuntimeError, match="compact failed"):
        client.post(
            f"/cards/{first['id']}/move",
            json={"column_id": target["id"], "position": 0},
        )

    assert calls["n"] >= 2
    assert cards_in(client, source["id"]) == [("A", 0), ("B", 3)]
    assert cards_in(client, target["id"]) == [("X", 2), ("Y", 7)]
    assert cards_in(client, untouched["id"]) == [("Z", 4)]
    assert client.get(f"/cards/{first['id']}").json()["column_id"] == source["id"]


def test_failed_column_move_leaves_the_board_unchanged(client, monkeypatch):
    add_column(client, "A", position=0)
    second = add_column(client, "B", position=4)
    third = add_column(client, "C", position=8)
    card = add_card(client, second["id"], title="Stay", position=6)

    def fail(*_args, **_kwargs):
        raise RuntimeError("compact failed")

    monkeypatch.setattr("app.ordering.compact_column_positions", fail)

    with pytest.raises(RuntimeError, match="compact failed"):
        client.post(f"/columns/{third['id']}/move", json={"position": 0})

    assert column_order(client) == [("A", 0), ("B", 4), ("C", 8)]
    assert client.get(f"/cards/{card['id']}").json()["position"] == 6
    assert client.get(f"/cards/{card['id']}").json()["column_id"] == second["id"]
