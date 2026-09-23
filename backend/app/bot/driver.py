import shutil

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from app.config import HEADLESS, PROFILE_DIR

BROWSER_BINARIES = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)


def build_chrome_driver() -> webdriver.Chrome:
    """Build a Chrome/Chromium driver that works on both Windows and Linux.

    Linux distros ship the browser as `chromium` rather than `google-chrome`, which is
    the only name Selenium looks for by default, so the binary is resolved explicitly.
    """
    options = Options()
    # A throwaway profile scores badly with Renfe's reCAPTCHA and drops the session on
    # every run, so the browser keeps its state in one directory instead.
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")

    for binary in BROWSER_BINARIES:
        path = shutil.which(binary)
        if path:
            options.binary_location = path
            break

    # Headless is opt-in only: the user finishes the purchase by hand in this window.
    if HEADLESS:
        options.add_argument("--headless=new")

    driver_path = shutil.which("chromedriver")
    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)
    return webdriver.Chrome(options=options)
