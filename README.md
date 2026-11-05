# mini-kanban

Small kanban API for columns and cards. `GET /health` reports whether the app is up. This version does not move cards between columns or reorder rows that are already stored.

## Install

Requires Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000`. `GET /health` returns `{"status": "ok"}` with HTTP 200.

The SQLite file defaults to `./kanban.db` in the working directory. Set `DATABASE_URL` to use another path, for example:

```bash
DATABASE_URL=sqlite:///./kanban.db uvicorn app.main:app --reload
```

On startup the app creates any missing tables. Starting again leaves existing tables in place.

## Test

```bash
pytest
```

## Columns

| Method | Path | Result |
| --- | --- | --- |
| `POST` | `/columns` | Create a column. HTTP 201. |
| `GET` | `/columns` | List columns ordered by `position`. HTTP 200. |
| `GET` | `/columns/{id}` | Fetch one column. HTTP 404 when it does not exist. |
| `PATCH` | `/columns/{id}` | Change `title`. HTTP 200. |
| `DELETE` | `/columns/{id}` | Delete the column and its cards. HTTP 204. |

`POST /columns` requires `title` (1 to 200 characters). `position` is optional. Omit it, or send `null`, and the column is appended after the highest existing column position. The first column is position `0`. `position` less than `0` is HTTP 422. A missing column is HTTP 404.

`PATCH /columns/{id}` accepts `title` only. If the body includes `position`, `column_id`, `status`, or any other field, the response is HTTP 422 and the column is left unchanged.

## Cards

| Method | Path | Result |
| --- | --- | --- |
| `POST` | `/cards` | Create a card. HTTP 201. |
| `GET` | `/cards` | List cards. Filter with `?column_id=`. HTTP 200. |
| `GET` | `/columns/{id}/cards` | List the cards in one column, ordered by `position`. HTTP 200. |
| `GET` | `/cards/{id}` | Fetch one card. HTTP 404 when it does not exist. |
| `PATCH` | `/cards/{id}` | Change `title` and/or `description`. HTTP 200. |
| `DELETE` | `/cards/{id}` | Delete the card and pack positions in its column. HTTP 204. |

`POST /cards` requires `title` and `column_id`. `description` is optional and may be `null`, up to 1000 characters. `position` is optional and, when omitted or `null`, appends the card after the last card in that column. An unknown `column_id` is HTTP 404. A missing required field, a negative `position`, or a `description` longer than 1000 characters is HTTP 422.

`GET /cards` returns cards in column order, then card `position`. `GET /cards?column_id={id}` and `GET /columns/{id}/cards` return one column. An unknown column is HTTP 404. An empty column is HTTP 200 and `[]`.

`PATCH /cards/{id}` accepts `title` and `description` only. `description` may be set to `null`. If the body includes `position`, `column_id`, `status`, or any other field, the response is HTTP 422 and the card is left unchanged.

`DELETE /cards/{id}` removes the card, then renumbers the remaining cards in that column to 0, 1, 2, and so on, keeping their previous order. Cards that shared a position stay in id order. Both writes commit in the same transaction, so a failed renumber leaves the card in place. Cards in other columns are not renumbered. Column positions are left as they are when a column is deleted.

Deleting a column removes its cards. Fetching one of those cards afterward is HTTP 404.

## Data

Startup creates two tables:

| Table | Columns |
| --- | --- |
| `columns` | `id`, `title`, `position`, `created_at`, `updated_at` |
| `cards` | `id`, `column_id`, `title`, `description`, `position`, `created_at`, `updated_at` |

`position` is an integer: board order for columns, and order within a column for cards. `created_at` and `updated_at` are ISO-8601 UTC timestamps such as `2026-11-04T14:48:00Z`.
