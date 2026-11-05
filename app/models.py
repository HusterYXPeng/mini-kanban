"""Kanban tables. Position is an integer so later move/reorder work can order rows."""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now_iso() -> str:
    """Current time as ISO-8601 UTC, for example 2026-11-04T14:48:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Column(Base):
    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso
    )

    cards: Mapped[list["Card"]] = relationship(
        back_populates="column",
        cascade="all, delete-orphan",
    )


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (Index("ix_cards_column_id_position", "column_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    column_id: Mapped[int] = mapped_column(
        ForeignKey("columns.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(
        String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso
    )

    column: Mapped[Column] = relationship(back_populates="cards")
