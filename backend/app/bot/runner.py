import asyncio
import logging
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.bot.events import TERMINAL_STATES, JobState
from app.bot.renfe import (
    CodePrompt,
    JobCancelled,
    LoginFailed,
    SearchRequest,
    run_search,
)

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 200


class JobConflict(Exception):
    """Raised when a requested action does not apply to the current job state."""


class JobManager:
    """Owns the single Selenium job and fans its progress out to WebSocket clients.

    Only one job may run at a time because each one drives a visible browser window
    that the user finishes the purchase in.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
        self._job: dict[str, Any] | None = None
        self._cancel = threading.Event()
        self._release = threading.Event()
        self._code_prompt = CodePrompt()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def start(self, request: SearchRequest, username: str) -> dict[str, Any]:
        with self._lock:
            if self._is_active():
                raise JobConflict("Ya hay una búsqueda en curso")

            self._cancel = threading.Event()
            self._release = threading.Event()
            self._code_prompt = CodePrompt()
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
            }
            thread = threading.Thread(
                target=self._run,
                args=(request, self._cancel, self._release, self._code_prompt),
                name="renfe-bot",
                daemon=True,
            )
            thread.start()
            return self.status()

    def cancel(self) -> None:
        with self._lock:
            if not self._is_active():
                raise JobConflict("No hay ninguna búsqueda activa")
            self._cancel.set()

    def release(self) -> None:
        """Let the worker close the browser once the user has finished the purchase."""
        with self._lock:
            if self._job is None or self._job["state"] != JobState.RESERVED:
                raise JobConflict("No hay ninguna reserva esperando confirmación")
            self._release.set()

    def submit_code(self, code: str) -> None:
        """Hand a verification code to the worker, which is parked waiting for it."""
        with self._lock:
            prompt = self._code_prompt
        prompt.submit(code)

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

    def _run(
        self,
        request: SearchRequest,
        cancel: threading.Event,
        release: threading.Event,
        code_prompt: CodePrompt,
    ) -> None:
        reporter = _ManagerReporter(self)
        try:
            run_search(request, reporter, cancel, release, code_prompt)
            reporter.state(JobState.FINISHED, "Navegador cerrado")
        except JobCancelled:
            reporter.state(JobState.CANCELLED, "Búsqueda detenida")
        except LoginFailed as exc:
            # Already phrased for the user; the type name would only add noise.
            logger.warning("Renfe login failed: %s", exc)
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

    def _publish(self, event: dict[str, Any]) -> None:
        payload = {"ts": _now(), **event}
        self._history.append(payload)
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


job_manager = JobManager()
