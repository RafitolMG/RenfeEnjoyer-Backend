import threading

import pytest
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

from app.bot import renfe

EMAIL = "viajero@example.com"


class FakeField:
    """A Renfe login input that swallows keystrokes until its scripts are bound."""

    def __init__(self, accepts_from_attempt: int = 1, stale_attempts: int = 0) -> None:
        self.accepts_from_attempt = accepts_from_attempt
        self.stale_attempts = stale_attempts
        self.attempts = 0
        self.value = ""

    def click(self) -> None:
        pass

    def clear(self) -> None:
        self.value = ""

    def send_keys(self, text: str) -> None:
        self.attempts += 1
        if self.attempts <= self.stale_attempts:
            raise StaleElementReferenceException("form re-rendered")
        if self.attempts >= self.accepts_from_attempt:
            self.value = text

    def get_attribute(self, name: str) -> str:
        return self.value if name == "value" else ""


class FakeWait:
    def __init__(self, field: FakeField) -> None:
        self.field = field

    def until(self, condition: object) -> FakeField:
        return self.field


class FakeDriver:
    def __init__(self, script_works: bool = True) -> None:
        self.script_works = script_works
        self.script_calls = 0

    def execute_script(self, script: str, field: FakeField, value: str) -> None:
        self.script_calls += 1
        if self.script_works:
            field.value = value


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renfe, "FIELD_RETRY_DELAY", 0)


def fill(
    driver: FakeDriver, field: FakeField, value: str = EMAIL, name: str = "num_tarjeta"
) -> None:
    renfe.fill_field(driver, FakeWait(field), name, value, threading.Event())


def test_fills_on_the_first_attempt() -> None:
    field, driver = FakeField(), FakeDriver()
    fill(driver, field)

    assert field.value == EMAIL
    assert driver.script_calls == 0


def test_retries_until_the_field_stops_dropping_keystrokes() -> None:
    """The reported symptom: several browser sessions before the input took."""
    field, driver = FakeField(accepts_from_attempt=3), FakeDriver(script_works=False)
    fill(driver, field)

    assert field.value == EMAIL
    assert field.attempts == 3


def test_falls_back_to_scripted_assignment() -> None:
    field, driver = FakeField(accepts_from_attempt=99), FakeDriver(script_works=True)
    fill(driver, field)

    assert field.value == EMAIL
    assert driver.script_calls == 1


def test_recovers_when_the_form_re_renders() -> None:
    field, driver = FakeField(stale_attempts=2), FakeDriver()
    fill(driver, field)

    assert field.value == EMAIL


def test_gives_up_without_leaking_the_value() -> None:
    field = FakeField(accepts_from_attempt=99)
    driver = FakeDriver(script_works=False)

    with pytest.raises(renfe.LoginFailed) as failure:
        fill(driver, field, value="ContrasenaSecreta", name="pass-login")

    assert "ContrasenaSecreta" not in str(failure.value)
    assert "pass-login" in str(failure.value)
    assert field.attempts == renfe.FIELD_FILL_ATTEMPTS


def test_cancelling_interrupts_the_retries() -> None:
    cancel = threading.Event()
    cancel.set()
    field = FakeField(accepts_from_attempt=99)

    with pytest.raises(renfe.JobCancelled):
        renfe.fill_field(FakeDriver(False), FakeWait(field), "num_tarjeta", EMAIL, cancel)


class InterceptedElement:
    """An element Selenium reports as clickable but that an overlay covers."""

    def __init__(self, intercepts: bool) -> None:
        self.intercepts = intercepts
        self.native_clicks = 0

    def click(self) -> None:
        self.native_clicks += 1
        if self.intercepts:
            raise ElementClickInterceptedException("element click intercepted")


class RecordingDriver:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def execute_script(self, script: str, *args: object) -> None:
        self.scripts.append(script)


def test_click_prefers_the_native_click() -> None:
    element, driver = InterceptedElement(intercepts=False), RecordingDriver()
    renfe._click(driver, element)

    assert element.native_clicks == 1
    assert driver.scripts == []


def test_click_falls_back_to_script_when_an_overlay_intercepts() -> None:
    """Renfe's cookie banner covers its own reject button; this is what killed runs."""
    element, driver = InterceptedElement(intercepts=True), RecordingDriver()
    renfe._click(driver, element)

    assert element.native_clicks == 1
    assert len(driver.scripts) == 1
