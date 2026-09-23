import hashlib
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from app.bot.errors import BotError
from app.config import HEADLESS, PROFILE_DIR

logger = logging.getLogger(__name__)

BROWSER_BINARIES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


# Written by the bot when it has seen the session work. The profile directory alone says
# nothing: Chrome fills it the moment it opens, logged in or not.
SESSION_MARKER = "renfe-session-verified"


class BrowserUnavailable(BotError):
    """Raised when the browser exits before Selenium can drive it."""


def profile_dir_for(account: str) -> Path:
    """One browser profile per Renfe account.

    A single shared profile would let a stored session leak across saved profiles: the
    session check only sees that *a* session is open, not whose, so the bot would happily
    search on the wrong account.
    """
    digest = hashlib.sha256(account.strip().lower().encode()).hexdigest()[:16]
    return PROFILE_DIR / digest


def mark_session_verified(profile_dir: Path) -> None:
    (profile_dir / SESSION_MARKER).write_text(datetime.now(UTC).isoformat())


def forget_session(profile_dir: Path) -> None:
    (profile_dir / SESSION_MARKER).unlink(missing_ok=True)


def session_verified_at(profile_dir: Path) -> str | None:
    """When the bot last saw this profile's Renfe session work, if it ever did."""
    try:
        return (profile_dir / SESSION_MARKER).read_text().strip() or None
    except FileNotFoundError:
        return None


def build_chrome_driver(profile_dir: Path) -> webdriver.Chrome:
    """Build a Chrome/Chromium driver that works on both Windows and Linux.

    Linux distros ship the browser as `chromium` rather than `google-chrome`, which is
    the only name Selenium looks for by default, so the binary is resolved explicitly.
    """
    options = Options()
    # A throwaway profile scores badly with Renfe's reCAPTCHA and drops the session on
    # every run, so the browser keeps its state between searches.
    profile_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")

    for binary in BROWSER_BINARIES:
        path = shutil.which(binary)
        if path:
            options.binary_location = path
            break

    # Headless is opt-in only: the user finishes the purchase by hand in this window.
    if HEADLESS:
        options.add_argument("--headless=new")

    # Without a system chromedriver, a None path lets Selenium Manager fetch one.
    service = Service(shutil.which("chromedriver"), env=browser_environment())
    try:
        return webdriver.Chrome(service=service, options=options)
    except SessionNotCreatedException as exc:
        logger.warning("Browser failed to start: %s", exc.msg)
        raise BrowserUnavailable(
            "No se pudo abrir el navegador. Lo más habitual es que no haya una sesión "
            "de escritorio iniciada en el equipo donde corre el bot; el detalle está en "
            "el registro del servidor."
        ) from exc


def browser_environment() -> dict[str, str]:
    """Environment for the browser, pointed at the desktop session when it lacks one.

    The server may be started outside the desktop (a terminal, a service, SSH) and then
    has no display for a visible browser, which exits the moment it starts. When a
    Wayland session is running for this user, the browser opens its window there.
    """
    env = dict(os.environ)
    if HEADLESS or env.get("WAYLAND_DISPLAY") or env.get("DISPLAY"):
        return env

    runtime_dir = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    sockets = sorted(
        path.name for path in runtime_dir.glob("wayland-*") if path.is_socket()
    )
    if sockets:
        env["XDG_RUNTIME_DIR"] = str(runtime_dir)
        env["WAYLAND_DISPLAY"] = sockets[0]
    return env
