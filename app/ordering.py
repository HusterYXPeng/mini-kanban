"""Position assignment for columns and cards.

Creating a row without `position` appends it after the current maximum in that
scope (all columns, or the cards in one column). The first row in a scope is
position 0.

Deleting a card, or moving a card or column, rewrites the affected positions
to 0, 1, 2, and so on. The caller commits that rewrite with the delete or move.
"""

from collections.abc import Sequence

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
    including a card delete or move, uncommitted.
    """
    cards = session.scalars(
        select(Card)
        .where(Card.column_id == column_id)
        .order_by(Card.position, Card.id)
    ).all()
    for index, card in enumerate(cards):
        if card.position != index:
            card.position = index


def compact_column_positions(session: Session) -> None:
    """Renumber every column to 0..n-1, preserving board order.

    Does not commit. A failure here leaves the surrounding column move
    uncommitted. Card positions are left alone.
    """
    columns = session.scalars(select(Column).order_by(Column.position, Column.id)).all()
    for index, column in enumerate(columns):
        if column.position != index:
            column.position = index


def move_card(session: Session, card: Card, column_id: int, position: int) -> None:
    """Insert `card` at `position` in `column_id`, then compact affected columns.

    `position` is the index among the other cards in the destination column,
    in list order (position, then id). A value past the end appends the card.
    The destination column is compacted once. A cross-column move also compacts
    the source column. Flushes so those compact queries see the insert. Does
    not commit.
    """
    source_column_id = card.column_id
    others = session.scalars(
        select(Card)
        .where(Card.column_id == column_id, Card.id != card.id)
        .order_by(Card.position, Card.id)
    ).all()
    card.column_id = column_id
    _stage_insert(card, others, position)
    # autoflush is off, so compact would otherwise order by the pre-move rows.
    session.flush()
    compact_card_positions(session, column_id)
    if source_column_id != column_id:
        compact_card_positions(session, source_column_id)


def move_column(session: Session, column: Column, position: int) -> None:
    """Insert `column` at `position` on the board, then compact column positions.

    `position` is the index among the other columns. A value past the end
    appends the column. Card positions are not rewritten. Flushes so the
    compact query sees the new order. Does not commit.
    """
    others = session.scalars(
        select(Column).where(Column.id != column.id).order_by(Column.position, Column.id)
    ).all()
    _stage_insert(column, others, position)
    session.flush()
    compact_column_positions(session)


def _stage_insert(item: Card | Column, others: Sequence[Card | Column], index: int) -> None:
    """Give `item` a sort key that lands at `index` before compaction.

    The other rows keep their relative order on the odd positions 1, 3, 5, ...
    and the inserted row takes the even slot in front of the displaced row.
    An index past the end sorts after the last row. Compaction then rewrites
    the sequence to 0..n-1.
    """
    bounded = min(index, len(others))
    for offset, other in enumerate(others):
        other.position = offset * 2 + 1
    item.position = bounded * 2
