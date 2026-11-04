"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import get_database_url, init_db, make_engine, make_session_factory


def create_app(database_url: str | None = None) -> FastAPI:
    """Build the API. Missing tables are created the first time the app starts."""
    url = database_url or get_database_url()
    engine = make_engine(url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db(engine)
        yield
        engine.dispose()

    app = FastAPI(title="mini-kanban", lifespan=lifespan)
    app.state.database_url = url
    app.state.engine = engine
    app.state.session_factory = session_factory

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
