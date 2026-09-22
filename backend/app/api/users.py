from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.db.models import User
from app.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(session: SessionDep) -> list[User]:
    return list(session.exec(select(User).order_by(User.username)).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: SessionDep) -> User:
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ya existe un perfil con ese nombre"
        )

    user = User.model_validate(payload)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, session: SessionDep) -> User:
    user = _get_or_404(session, user_id)

    changes = payload.model_dump(exclude_unset=True)
    # A blank password means "keep the stored one" — the client never receives it.
    if not changes.get("password"):
        changes.pop("password", None)

    for field, value in changes.items():
        if value is not None:
            setattr(user, field, value)

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, session: SessionDep) -> None:
    session.delete(_get_or_404(session, user_id))
    session.commit()


def _get_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado")
    return user
