import threading

import pytest
from fastapi.testclient import TestClient

from app.bot.events import JobState
from app.config import PROFILE_DIR


@pytest.fixture
def stored_profile() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    (PROFILE_DIR / "Default").mkdir(exist_ok=True)
    (PROFILE_DIR / "Default" / "Cookies").write_text("stub")


def test_reports_when_no_session_is_stored(client: TestClient) -> None:
    import shutil

    shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    assert client.get("/api/session").json() == {"stored": False}


def test_reports_and_clears_a_stored_session(
    client: TestClient, stored_profile: None
) -> None:
    assert client.get("/api/session").json() == {"stored": True}
    assert client.delete("/api/session").status_code == 204
    assert not PROFILE_DIR.exists()


def test_session_is_not_cleared_while_a_search_runs(
    client: TestClient,
    profile: dict,
    stored_profile: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The running browser holds the profile open, so clearing it would break the job."""
    started = threading.Event()

    def blocking_run_search(request, reporter, cancel, release, code_prompt) -> None:
        reporter.state(JobState.POLLING, "Buscando plazas")
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr("app.bot.runner.run_search", blocking_run_search)
    client.post(
        "/api/jobs/current",
        json={
            "user_id": profile["id"],
            "departure_time": "07:30",
            "journey_type": "ida",
            "date": "01/10/2026",
        },
    )
    assert started.wait(timeout=5)

    assert client.delete("/api/session").status_code == 409
    assert PROFILE_DIR.exists()

    client.post("/api/jobs/current/stop")
