import shutil

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.bot.driver import profile_dir_for, session_verified_at
from app.bot.runner import job_manager
from app.db.models import User

router = APIRouter(prefix="/api/users/{user_id}/session", tags=["session"])


@router.get("")
def read_session(user_id: int, session: SessionDep) -> dict[str, bool | str | None]:
    """Whether the bot has seen this profile's session work, and when it last did.

    A verified session can still have expired since; only the next search can tell.
    """
    verified_at = session_verified_at(
        profile_dir_for(_get_or_404(session, user_id).email)
    )
    return {"stored": verified_at is not None, "verified_at": verified_at}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_session(user_id: int, session: SessionDep) -> None:
    """Drop this account's browser profile, forcing a fresh login on the next search."""
    if job_manager.is_active():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Hay una búsqueda en curso usando el navegador",
        )
    shutil.rmtree(
        profile_dir_for(_get_or_404(session, user_id).email), ignore_errors=True
    )


def _get_or_404(session: SessionDep, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado")
    return user
