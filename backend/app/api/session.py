import shutil

from fastapi import APIRouter, HTTPException, status

from app.bot.runner import job_manager
from app.config import PROFILE_DIR

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("")
def read_session() -> dict[str, bool]:
    return {"stored": PROFILE_DIR.is_dir() and any(PROFILE_DIR.iterdir())}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_session() -> None:
    """Drop the stored browser profile, forcing a fresh login on the next search."""
    if job_manager.is_active():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Hay una búsqueda en curso usando el navegador",
        )
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)
