from typing import Literal

from pydantic import Field
from sqlmodel import SQLModel

from app.db.models import UserBase


class UserCreate(UserBase):
    pass


class UserUpdate(SQLModel):
    username: str | None = None
    email: str | None = None
    password: str | None = None
    abono: str | None = None


class UserRead(SQLModel):
    """Public view of a profile. The Renfe password is never sent to the client."""

    id: int
    username: str
    email: str
    abono: str


class JobStartRequest(SQLModel):
    user_id: int
    departure_time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    journey_type: Literal["ida", "vuelta"]
    date: str = Field(pattern=r"^\d{2}/\d{2}/\d{4}$")


class VerificationCode(SQLModel):
    code: str = Field(min_length=4, max_length=12, pattern=r"^[A-Za-z0-9]+$")
