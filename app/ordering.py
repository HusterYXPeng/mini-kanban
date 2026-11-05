"""Position assignment for columns and cards.

Creating a row without `position` appends it after the current maximum in that
scope (all columns, or the cards in one column). The first row in a scope is
position 0. Deleting a card rewrites the remaining cards in its column to
0, 1, 2, and so on. The caller commits that rewrite with the delete.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Card, Column


def next_column_position(session: Session) -> int:
    """Return the position after the last column, or 0 when the board is empty."""
    current = session.scalar(select(func.max(Column.position)))
    if current is None:
        return 0
    return current + 1


def next_card_position(session: Session, column_id: int) -> int:
    """Return the position after the last card in a column, or 0 when it is empty."""
    current = session.scalar(
        select(func.max(Card.position)).where(Card.column_id == column_id)
    )
    if current is None:
        return 0
    return current + 1


def compact_card_positions(session: Session, column_id: int) -> None:
    """Renumber one column's cards to 0..n-1, preserving their previous order.

    Does not commit. A failure here leaves the surrounding transaction,
    including a card delete, uncommitted.
    """
    cards = session.scalars(
        select(Card)
        .where(Card.column_id == column_id)
        .order_by(Card.position, Card.id)
    ).all()
    for index, card in enumerate(cards):
        if card.position != index:
            card.position = index
