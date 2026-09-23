from pathlib import Path

import pytest

from app.bot import renfe
from app.bot.driver import mark_session_verified, session_verified_at

REQUEST = renfe.SearchRequest(
    departure_time=None,
    journey_type="ida",
    date="01/10/2026",
    email="viajero@example.com",
    password="secreto",
    abono="ABONO123",
)


class LandingDriver:
    """Loads any URL and ends up on `landing`, as Renfe's redirects would."""

    def __init__(self, landing: str) -> None:
        self.landing = landing
        self.current_url = ""

    def get(self, url: str) -> None:
        self.current_url = self.landing


class NullReporter:
    def state(self, state: object, message: str) -> None: ...
    def log(self, message: str) -> None: ...
    def attempt(self, count: int) -> None: ...
    def trains(self, trains: list) -> None: ...


@pytest.fixture
def profile_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(renfe, "profile_dir_for", lambda email: tmp_path)
    monkeypatch.setattr(renfe, "_dismiss_cookie_banner", lambda driver, reporter: None)
    return tmp_path


def ensure_session(driver: LandingDriver) -> None:
    renfe._ensure_session(driver, None, REQUEST, NullReporter(), renfe.Interaction())


def test_a_session_that_works_is_recorded(profile_dir: Path) -> None:
    ensure_session(LandingDriver(renfe.PASSES_URL))
    assert session_verified_at(profile_dir) is not None


def test_an_expired_session_is_forgotten_before_logging_in_again(
    profile_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mark_session_verified(profile_dir)
    seen_during_login: list[str | None] = []
    monkeypatch.setattr(
        renfe,
        "_login",
        lambda *args: seen_during_login.append(session_verified_at(profile_dir)),
    )

    ensure_session(LandingDriver("https://www.renfe.com/es/es"))

    assert seen_during_login == [None]
    assert session_verified_at(profile_dir) is not None


def test_a_login_stuck_on_the_captcha_leaves_no_session_behind(
    profile_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def stopped_by_the_user(*args: object) -> None:
        raise renfe.JobCancelled

    mark_session_verified(profile_dir)
    monkeypatch.setattr(renfe, "_login", stopped_by_the_user)

    with pytest.raises(renfe.JobCancelled):
        ensure_session(LandingDriver("https://www.renfe.com/es/es"))

    assert session_verified_at(profile_dir) is None
