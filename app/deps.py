"""Request-scoped database sessions."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """Yield a session and roll it back when the request raises."""
    session = request.app.state.session_factory()
    session.expire_on_commit = False
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
