import threading

import pytest
from fastapi.testclient import TestClient

from app.bot.events import JobState
from app.bot.renfe import CodePrompt, SearchRequest, run_search
from app.bot.runner import JobConflict, JobManager


def test_no_job_is_idle(client: TestClient) -> None:
    assert client.get("/api/jobs/current").json()["state"] == "idle"


def test_start_with_unknown_profile_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/jobs/current",
        json={
            "user_id": 999,
            "departure_time": "07:30",
            "journey_type": "ida",
            "date": "01/10/2026",
        },
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("departure_time", "7h30"),
        ("journey_type", "lateral"),
        ("date", "2026-10-01"),
    ],
)
def test_malformed_search_is_rejected(
    client: TestClient, profile: dict, field: str, value: str
) -> None:
    payload = {
        "user_id": profile["id"],
        "departure_time": "07:30",
        "journey_type": "ida",
        "date": "01/10/2026",
    }
    payload[field] = value
    assert client.post("/api/jobs/current", json=payload).status_code == 422


def test_stop_without_a_job_conflicts(client: TestClient) -> None:
    assert client.post("/api/jobs/current/stop").status_code == 409


def test_release_without_a_reservation_conflicts(client: TestClient) -> None:
    assert client.post("/api/jobs/current/release").status_code == 409


def test_manager_starts_idle() -> None:
    assert JobManager().status()["state"] == "idle"


def test_manager_rejects_release_when_idle() -> None:
    with pytest.raises(JobConflict):
        JobManager().release()


def test_invalid_journey_type_fails_before_opening_a_browser() -> None:
    """Guards the browser launch, which is the expensive part of a bad request."""
    request = SearchRequest(
        departure_time="07:30",
        journey_type="diagonal",
        date="01/10/2026",
        email="a@b.c",
        password="x",
        abono="ABC",
    )
    with pytest.raises(ValueError, match="Invalid journey type"):
        run_search(
            request,
            _NullReporter(),
            threading.Event(),
            threading.Event(),
            CodePrompt(),
        )


class _NullReporter:
    def state(self, state: JobState, message: str) -> None: ...
    def log(self, message: str) -> None: ...
    def attempt(self, count: int) -> None: ...


def test_stream_replays_current_state_on_connect(client: TestClient) -> None:
    with client.websocket_connect("/api/jobs/stream") as websocket:
        snapshot = websocket.receive_json()

    assert snapshot["type"] == "snapshot"
    assert snapshot["status"]["state"] == "idle"
    assert snapshot["events"] == []


def test_progress_streams_over_the_websocket(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the full path: worker thread -> event loop -> connected client."""

    def fake_run_search(request, reporter, cancel, release, code_prompt) -> None:
        reporter.state(JobState.POLLING, "Buscando plazas")
        reporter.attempt(1)
        reporter.log("Intento 1: tren no disponible, recargando")

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)

    with client.websocket_connect("/api/jobs/stream") as websocket:
        assert websocket.receive_json()["type"] == "snapshot"

        started = client.post(
            "/api/jobs/current",
            json={
                "user_id": profile["id"],
                "departure_time": "07:30",
                "journey_type": "ida",
                "date": "01/10/2026",
            },
        )
        assert started.status_code == 202
        assert started.json()["search"]["username"] == "demo"

        received = []
        while True:
            event = websocket.receive_json()
            received.append(event)
            if event.get("state") in {"finished", "failed"}:
                break

    assert [e["type"] for e in received] == ["state", "attempt", "log", "state"]
    assert received[0]["state"] == "polling"
    assert received[1]["attempts"] == 1
    assert received[-1]["state"] == "finished"


def test_second_job_is_rejected_while_one_runs(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()

    def blocking_run_search(request, reporter, cancel, release, code_prompt) -> None:
        reporter.state(JobState.RESERVED, "Plaza reservada")
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr("app.bot.runner.run_search", blocking_run_search)

    payload = {
        "user_id": profile["id"],
        "departure_time": "07:30",
        "journey_type": "ida",
        "date": "01/10/2026",
    }
    assert client.post("/api/jobs/current", json=payload).status_code == 202
    assert started.wait(timeout=5)

    assert client.post("/api/jobs/current", json=payload).status_code == 409
    assert client.post("/api/jobs/current/release").status_code == 202


def test_code_is_rejected_when_none_is_awaited(client: TestClient) -> None:
    response = client.post("/api/jobs/current/code", json={"code": "123456"})
    assert response.status_code == 409


@pytest.mark.parametrize("code", ["12", "código!", "", "1234567890123"])
def test_malformed_codes_are_rejected(client: TestClient, code: str) -> None:
    assert client.post("/api/jobs/current/code", json={"code": code}).status_code == 422


def test_verification_code_reaches_the_waiting_bot(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bot parks on the prompt; an API request hands it the code from the UI."""
    asked = threading.Event()
    consumed = threading.Event()
    received: list[str] = []

    def fake_run_search(request, reporter, cancel, release, code_prompt) -> None:
        code_prompt.request()
        reporter.state(JobState.AWAITING_CODE, "Renfe pide un código de verificación")
        asked.set()
        received.append(code_prompt.wait(cancel))
        consumed.set()

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)

    started = client.post(
        "/api/jobs/current",
        json={
            "user_id": profile["id"],
            "departure_time": "07:30",
            "journey_type": "ida",
            "date": "01/10/2026",
        },
    )
    assert started.status_code == 202
    assert asked.wait(timeout=5)
    assert client.get("/api/jobs/current").json()["state"] == "awaiting_code"

    assert (
        client.post("/api/jobs/current/code", json={"code": "483920"}).status_code == 202
    )
    assert consumed.wait(timeout=5)
    assert received == ["483920"]


def test_a_second_code_is_rejected_once_the_first_is_consumed(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = threading.Event()
    consumed = threading.Event()

    def fake_run_search(request, reporter, cancel, release, code_prompt) -> None:
        code_prompt.request()
        reporter.state(JobState.AWAITING_CODE, "Código requerido")
        asked.set()
        code_prompt.wait(cancel)
        consumed.set()
        release.wait(timeout=5)

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)
    client.post(
        "/api/jobs/current",
        json={
            "user_id": profile["id"],
            "departure_time": "07:30",
            "journey_type": "ida",
            "date": "01/10/2026",
        },
    )
    assert asked.wait(timeout=5)
    assert (
        client.post("/api/jobs/current/code", json={"code": "111111"}).status_code == 202
    )
    assert consumed.wait(timeout=5)

    assert (
        client.post("/api/jobs/current/code", json={"code": "222222"}).status_code == 409
    )
