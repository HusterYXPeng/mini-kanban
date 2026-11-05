"""Card create, list, fetch, update, and delete routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ordering
from app.deps import get_session
from app.models import Card, Column, utc_now_iso
from app.schemas import CardCreate, CardRead, CardUpdate

router = APIRouter(tags=["cards"])


@router.post("/cards", response_model=CardRead, status_code=status.HTTP_201_CREATED)
def create_card(payload: CardCreate, session: Session = Depends(get_session)) -> Card:
    """Create a card. A missing position appends it within its column."""
    column = session.get(Column, payload.column_id)
    if column is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    position = payload.position
    if position is None:
        position = ordering.next_card_position(session, column.id)
    card = Card(
        column_id=column.id,
        title=payload.title,
        description=payload.description,
        position=position,
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@router.get("/cards", response_model=list[CardRead])
def list_cards(
    column_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[Card]:
    """Return cards in board order, or only the cards in `column_id`."""
    if column_id is None:
        stmt = (
            select(Card)
            .join(Card.column)
            .order_by(Column.position, Card.position, Card.id)
        )
        return list(session.scalars(stmt).all())
    return _cards_in_column(session, column_id)


@router.get("/columns/{column_id}/cards", response_model=list[CardRead])
def list_column_cards(column_id: int, session: Session = Depends(get_session)) -> list[Card]:
    """Return the cards in one column, ordered by position."""
    return _cards_in_column(session, column_id)


@router.get("/cards/{card_id}", response_model=CardRead)
def get_card(card_id: int, session: Session = Depends(get_session)) -> Card:
    """Return one card."""
    return _get_card(session, card_id)


@router.patch("/cards/{card_id}", response_model=CardRead)
def update_card(
    card_id: int,
    payload: CardUpdate,
    session: Session = Depends(get_session),
) -> Card:
    """Change a card title and/or description. Moves are not accepted."""
    card = _get_card(session, card_id)
    changed = False
    if "title" in payload.model_fields_set:
        card.title = payload.title
        changed = True
    if "description" in payload.model_fields_set:
        card.description = payload.description
        changed = True
    if changed:
        card.updated_at = utc_now_iso()
    session.commit()
    session.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, session: Session = Depends(get_session)) -> None:
    """Delete a card and pack the remaining positions in its column.

    The delete and the position rewrite commit together. A failure while
    packing rolls the delete back.
    """
    card = _get_card(session, card_id)
    column_id = card.column_id
    session.delete(card)
    session.flush()
    ordering.compact_card_positions(session, column_id)
    session.commit()


def _cards_in_column(session: Session, column_id: int) -> list[Card]:
    if session.get(Column, column_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    stmt = select(Card).where(Card.column_id == column_id).order_by(Card.position, Card.id)
    return list(session.scalars(stmt).all())


def _get_card(session: Session, card_id: int) -> Card:
    card = session.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card
