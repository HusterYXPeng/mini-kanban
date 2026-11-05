"""Request and response bodies for columns and cards."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

TITLE_MIN_LENGTH = 1
TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 1000


def _reject_null_title(value: str | None) -> str | None:
    if value is None:
        raise ValueError("title cannot be null")
    return value


class ColumnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH)
    position: int | None = Field(default=None, ge=0)


class ColumnUpdate(BaseModel):
    """Title-only update. `position`, `column_id`, and `status` are rejected."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
    )

    @field_validator("title")
    @classmethod
    def title_cannot_be_null(cls, value: str | None) -> str | None:
        return _reject_null_title(value)


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    position: int
    created_at: str
    updated_at: str


class CardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH)
    column_id: int
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    position: int | None = Field(default=None, ge=0)


class CardUpdate(BaseModel):
    """Title and description only. `position`, `column_id`, and `status` are rejected."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)

    @field_validator("title")
    @classmethod
    def title_cannot_be_null(cls, value: str | None) -> str | None:
        return _reject_null_title(value)


class CardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    column_id: int
    title: str
    description: str | None
    position: int
    created_at: str
    updated_at: str
