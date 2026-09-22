from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.api.deps import SessionDep
from app.bot.renfe import SearchRequest
from app.bot.runner import JobConflict, job_manager
from app.db.models import User
from app.schemas import JobStartRequest

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/current")
def get_current_job() -> dict[str, Any]:
    return job_manager.status()


@router.post("/current", status_code=status.HTTP_202_ACCEPTED)
def start_job(payload: JobStartRequest, session: SessionDep) -> dict[str, Any]:
    user = session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Perfil no encontrado")

    request = SearchRequest(
        departure_time=payload.departure_time,
        journey_type=payload.journey_type,
        date=payload.date,
        email=user.email,
        password=user.password,
        abono=user.abono,
    )
    try:
        return job_manager.start(request, user.username)
    except JobConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/current/stop", status_code=status.HTTP_202_ACCEPTED)
def stop_job() -> dict[str, Any]:
    try:
        job_manager.cancel()
    except JobConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return job_manager.status()


@router.post("/current/release", status_code=status.HTTP_202_ACCEPTED)
def release_job() -> dict[str, Any]:
    """Close the browser after the user has completed the purchase by hand."""
    try:
        job_manager.release()
    except JobConflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return job_manager.status()


@router.websocket("/stream")
async def stream_job(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = job_manager.subscribe()
    try:
        # Replay so a client joining mid-run still renders the full progress log.
        await websocket.send_json(
            {
                "type": "snapshot",
                "status": job_manager.status(),
                "events": job_manager.history(),
            }
        )
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        job_manager.unsubscribe(queue)
