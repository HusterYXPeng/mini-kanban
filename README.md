# mini-kanban

Small kanban API. This revision is the foundation: a FastAPI app, a SQLite database, and automatic table creation on startup.

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

## Data

Startup creates two tables:

| Table | Columns |
| --- | --- |
| `columns` | `id`, `title`, `position`, `created_at`, `updated_at` |
| `cards` | `id`, `column_id`, `title`, `description`, `position`, `created_at`, `updated_at` |

`position` is an integer: board order for columns, and order within a column for cards. `created_at` and `updated_at` are ISO-8601 UTC timestamps such as `2026-11-04T14:48:00Z`.
