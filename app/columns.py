"""Column create, list, fetch, update, and delete routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_session
from app.models import Column, utc_now_iso
from app.ordering import next_column_position
from app.schemas import ColumnCreate, ColumnRead, ColumnUpdate

router = APIRouter(tags=["columns"])


@router.post("/columns", response_model=ColumnRead, status_code=status.HTTP_201_CREATED)
def create_column(payload: ColumnCreate, session: Session = Depends(get_session)) -> Column:
    """Create a column. A missing position appends it to the board."""
    position = payload.position
    if position is None:
        position = next_column_position(session)
    column = Column(title=payload.title, position=position)
    session.add(column)
    session.commit()
    session.refresh(column)
    return column


@router.get("/columns", response_model=list[ColumnRead])
def list_columns(session: Session = Depends(get_session)) -> list[Column]:
    """Return every column in board order."""
    stmt = select(Column).order_by(Column.position, Column.id)
    return list(session.scalars(stmt).all())


@router.get("/columns/{column_id}", response_model=ColumnRead)
def get_column(column_id: int, session: Session = Depends(get_session)) -> Column:
    """Return one column."""
    return _get_column(session, column_id)


@router.patch("/columns/{column_id}", response_model=ColumnRead)
def update_column(
    column_id: int,
    payload: ColumnUpdate,
    session: Session = Depends(get_session),
) -> Column:
    """Change a column title. Position and other fields are not accepted."""
    column = _get_column(session, column_id)
    if "title" in payload.model_fields_set:
        column.title = payload.title
        column.updated_at = utc_now_iso()
    session.commit()
    session.refresh(column)
    return column


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(column_id: int, session: Session = Depends(get_session)) -> None:
    """Delete a column and, through the table cascade, its cards."""
    column = _get_column(session, column_id)
    session.delete(column)
    session.commit()


def _get_column(session: Session, column_id: int) -> Column:
    column = session.get(Column, column_id)
    if column is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return column
