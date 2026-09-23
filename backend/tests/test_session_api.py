import shutil
import threading

import pytest
from fastapi.testclient import TestClient

from app.bot.driver import profile_dir_for
from app.bot.events import JobState

ACCOUNT = "demo@example.com"


@pytest.fixture
def stored_profile() -> None:
    directory = profile_dir_for(ACCOUNT)
    (directory / "Default").mkdir(parents=True, exist_ok=True)
    (directory / "Default" / "Cookies").write_text("stub")


def test_profiles_never_share_a_browser_session() -> None:
    """A shared profile would let the bot search on whichever account logged in last."""
    assert profile_dir_for("uno@example.com") != profile_dir_for("dos@example.com")
    assert profile_dir_for("Uno@Example.com ") == profile_dir_for("uno@example.com")


def test_reports_when_nothing_is_stored(client: TestClient, profile: dict) -> None:
    shutil.rmtree(profile_dir_for(ACCOUNT), ignore_errors=True)
    response = client.get(f"/api/users/{profile['id']}/session")
    assert response.json() == {"stored": False}


def test_reports_and_clears_a_stored_session(
    client: TestClient, profile: dict, stored_profile: None
) -> None:
    assert client.get(f"/api/users/{profile['id']}/session").json() == {"stored": True}
    assert client.delete(f"/api/users/{profile['id']}/session").status_code == 204
    assert not profile_dir_for(ACCOUNT).exists()


def test_unknown_profile_returns_404(client: TestClient) -> None:
    assert client.get("/api/users/999/session").status_code == 404
    assert client.delete("/api/users/999/session").status_code == 404


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

    assert client.delete(f"/api/users/{profile['id']}/session").status_code == 409
    assert profile_dir_for(ACCOUNT).exists()

    client.post("/api/jobs/current/stop")
