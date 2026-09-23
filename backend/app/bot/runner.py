import asyncio
import logging
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.bot.events import TERMINAL_STATES, JobState
from app.bot.renfe import (
    BotError,
    Interaction,
    JobCancelled,
    PromptNotOpen,
    SearchRequest,
    Train,
    run_search,
)

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 200


class JobConflict(Exception):
    """Raised when a requested action does not apply to the current job state."""


class TrainNotListed(Exception):
    """Raised when the chosen departure is not one of the trains offered."""


class JobManager:
    """Owns the single Selenium job and fans its progress out to WebSocket clients.

    Only one job may run at a time because each one drives a visible browser window
    that the user finishes the purchase in.

    The WebSocket is the only source of truth for job state. Action endpoints return a
    status too, but a client that applied it could overwrite a newer state that the
    socket had already delivered.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self._job: dict[str, Any] | None = None
        self._interaction = Interaction()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def start(self, request: SearchRequest, username: str) -> dict[str, Any]:
        with self._lock:
            if self._is_active():
                raise JobConflict("Ya hay una búsqueda en curso")

            self._interaction = Interaction()
            self._history.clear()
            self._job = {
                "state": JobState.STARTING,
                "message": "Preparando la búsqueda",
                "attempts": 0,
                "started_at": _now(),
                "search": {
                    "username": username,
                    "departure_time": request.departure_time,
                    "journey_type": request.journey_type,
                    "date": request.date,
                    "abono": request.abono,
                },
                "trains": [],
            }
            # Sent before the worker starts, so clients reset their log ahead of the
            # new job's first event rather than after it.
            self._broadcast({"type": "snapshot", "status": self.status(), "events": []})

            thread = threading.Thread(
                target=self._run,
                args=(request, self._interaction),
                name="renfe-bot",
                daemon=True,
            )
            thread.start()
            return self.status()

    def cancel(self) -> None:
        with self._lock:
            if not self._is_active():
                raise JobConflict("No hay ninguna búsqueda activa")
            self._interaction.cancel.set()

    def release(self) -> None:
        """Let the worker close the browser once the user has finished the purchase."""
        with self._lock:
            if self._job is None or self._job["state"] != JobState.RESERVED:
                raise JobConflict("No hay ninguna reserva esperando confirmación")
            self._interaction.release.set()

    def submit_code(self, code: str) -> None:
        """Hand a verification code to the worker, which is parked waiting for it."""
        with self._lock:
            prompt = self._interaction.code
        prompt.submit(code)

    def submit_train(self, departure: str) -> None:
        """Tell the worker which of the listed trains to hunt a seat on."""
        with self._lock:
            job, prompt = self._job, self._interaction.train
            if job is None or not prompt.pending:
                raise PromptNotOpen("El bot no está esperando que elijas tren")
            if departure not in {train["departure"] for train in job["trains"]}:
                raise TrainNotListed(
                    f"No hay ningún tren listado con salida a las {departure}"
                )

            prompt.submit(departure)
            job["search"] = {**job["search"], "departure_time": departure}
            search = job["search"]
        self._broadcast({"type": "search", "search": search})

    def is_active(self) -> bool:
        with self._lock:
            return self._is_active()

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._job is None:
                return {"state": "idle", "message": "Sin búsquedas activas"}
            return dict(self._job)

    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def _run(self, request: SearchRequest, interaction: Interaction) -> None:
        reporter = _ManagerReporter(self)
        try:
            run_search(request, reporter, interaction)
            reporter.state(JobState.FINISHED, "Navegador cerrado")
        except JobCancelled:
            reporter.state(JobState.CANCELLED, "Búsqueda detenida")
        except BotError as exc:
            # Already phrased for the user; the type name would only add noise.
            logger.warning("Renfe job stopped: %s", exc)
            reporter.state(JobState.FAILED, str(exc))
        except Exception as exc:
            logger.exception("Renfe job failed")
            reporter.state(JobState.FAILED, f"{type(exc).__name__}: {exc}")

    def _is_active(self) -> bool:
        return self._job is not None and self._job["state"] not in TERMINAL_STATES

    def _set_state(self, state: JobState, message: str) -> None:
        with self._lock:
            if self._job is not None:
                self._job["state"] = state
                self._job["message"] = message
        self._publish({"type": "state", "state": state, "message": message})

    def _set_attempts(self, count: int) -> None:
        with self._lock:
            if self._job is not None:
                self._job["attempts"] = count
        self._publish({"type": "attempt", "attempts": count})

    def _set_trains(self, trains: list[Train]) -> None:
        with self._lock:
            if self._job is not None:
                self._job["trains"] = trains
        self._broadcast({"type": "trains", "trains": trains})

    def _publish(self, event: dict[str, Any]) -> None:
        """Record a log-worthy event for late joiners and send it to every client."""
        payload = {"ts": _now(), **event}
        self._history.append(payload)
        self._broadcast(payload)

    def _broadcast(self, payload: dict[str, Any]) -> None:
        """Send without recording: the status snapshot already carries this state."""
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._fanout, payload)

    def _fanout(self, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            queue.put_nowait(payload)


class _ManagerReporter:
    """Adapts JobManager to the Reporter protocol the bot flow expects."""

    def __init__(self, manager: JobManager) -> None:
        self._manager = manager

    def state(self, state: JobState, message: str) -> None:
        self._manager._set_state(state, message)

    def log(self, message: str) -> None:
        self._manager._publish({"type": "log", "message": message})

    def attempt(self, count: int) -> None:
        self._manager._set_attempts(count)

    def trains(self, trains: list[Train]) -> None:
        self._manager._set_trains(trains)


def _now() -> str:
    return datetime.now(UTC).isoformat()


job_manager = JobManager()
