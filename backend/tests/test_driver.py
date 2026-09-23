import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from selenium.common.exceptions import SessionNotCreatedException

from app.bot import driver
from app.bot.errors import BotError


@pytest.fixture
def bare_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A server started outside the desktop: no display variables at all."""
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(driver, "HEADLESS", False)
    return tmp_path


@pytest.fixture
def desktop_session(bare_environment: Path) -> Iterator[Path]:
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(bare_environment / "wayland-1"))
    (bare_environment / "wayland-1.lock").touch()
    yield bare_environment
    listener.close()


def test_a_server_outside_the_desktop_opens_the_browser_on_it(
    desktop_session: Path,
) -> None:
    env = driver.browser_environment()
    assert env["WAYLAND_DISPLAY"] == "wayland-1"
    assert env["XDG_RUNTIME_DIR"] == str(desktop_session)


def test_without_a_desktop_session_nothing_is_invented(bare_environment: Path) -> None:
    (bare_environment / "wayland-0").touch()  # a plain file, not a live socket
    assert "WAYLAND_DISPLAY" not in driver.browser_environment()


@pytest.mark.parametrize("variable", ["WAYLAND_DISPLAY", "DISPLAY"])
def test_a_display_the_server_already_has_is_left_alone(
    desktop_session: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "the-one-in-use")
    env = driver.browser_environment()
    assert env[variable] == "the-one-in-use"
    if variable == "DISPLAY":
        assert "WAYLAND_DISPLAY" not in env


def test_headless_runs_need_no_display(
    desktop_session: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(driver, "HEADLESS", True)
    assert "WAYLAND_DISPLAY" not in driver.browser_environment()


def test_the_rest_of_the_environment_is_passed_through(
    desktop_session: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Selenium uses this mapping instead of the process environment, not on top of it."""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert driver.browser_environment()["PATH"] == "/usr/bin:/bin"


def test_a_browser_that_dies_on_launch_is_reported_plainly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def exiting_browser(**kwargs: object) -> None:
        raise SessionNotCreatedException("session not created: Chrome instance exited")

    monkeypatch.setattr(driver.webdriver, "Chrome", exiting_browser)

    with pytest.raises(driver.BrowserUnavailable) as failure:
        driver.build_chrome_driver(tmp_path / "profile")

    assert isinstance(failure.value, BotError)
    assert "sesión de escritorio" in str(failure.value)
    assert "Chrome instance exited" not in str(failure.value)
