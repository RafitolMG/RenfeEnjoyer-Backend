from collections.abc import Callable

import pytest
from selenium.webdriver.common.by import By

from app.bot import renfe
from app.bot.events import JobState

VALID_CODE = "483920"
HOME_URL = "https://venta.renfe.com/vol/home.do"


class FakeElement:
    def __init__(
        self, displayed: bool = True, on_click: Callable[[], None] | None = None
    ) -> None:
        self.displayed = displayed
        self.on_click = on_click
        self.value = ""

    def is_displayed(self) -> bool:
        return self.displayed

    def is_enabled(self) -> bool:
        return True

    def click(self) -> None:
        if self.on_click is not None:
            self.on_click()

    def clear(self) -> None:
        self.value = ""

    def send_keys(self, text: str) -> None:
        self.value += text

    def get_attribute(self, name: str) -> str:
        return self.value if name == "value" else ""


class VerificationModal:
    """Renfe's two-step modal, looked up by the ids of the captured markup.

    Only the Validar button submits, and Renfe answers on the next lookup rather than
    at once. A previous verdict stays on screen until something hides it.
    """

    def __init__(self, attempts_allowed: int = 3) -> None:
        self.attempts_allowed = attempts_allowed
        self.current_url = renfe.LOGIN_URL
        self.codes_checked: list[str] = []
        self.failures = 0
        self.regenerated = 0
        self._pending: str | None = None

        self.field = FakeElement()
        self.rejected = FakeElement(displayed=False)
        self.exhausted = FakeElement(displayed=False)
        self.elements = {
            "codigoValidaLogin2F": self.field,
            "errorProcesoValidacionCodigo": self.rejected,
            "errorCampoCodigoVacio": FakeElement(displayed=False),
            "errorIntentosValidacion": self.exhausted,
            "idBotonValDispositivo": FakeElement(on_click=self._validate),
            "idBotonRegenerarCodigo": FakeElement(
                displayed=False, on_click=self._regenerate
            ),
        }

    def _validate(self) -> None:
        self._pending = self.field.value

    def _regenerate(self) -> None:
        self.regenerated += 1
        self.failures = 0
        self.exhausted.displayed = False

    def _answer(self) -> None:
        code, self._pending = self._pending, None
        if code is None:
            return
        self.codes_checked.append(code)
        if code == VALID_CODE:
            self.field.displayed = False
            self.current_url = HOME_URL
            return
        self.failures += 1
        if self.failures >= self.attempts_allowed:
            self.exhausted.displayed = True
        else:
            self.rejected.displayed = True

    def find_elements(self, by: str, value: str) -> list[FakeElement]:
        self._answer()
        if by == By.CSS_SELECTOR:
            ids = [part.strip().removeprefix("#") for part in value.split(",")]
        else:
            ids = [value]
        return [self.elements[i] for i in ids if i in self.elements]

    def find_element(self, by: str, value: str) -> FakeElement:
        return self.elements[value]

    def execute_script(self, script: str, *args: object) -> None:
        if isinstance(args[0], str):
            for label in self.find_elements(By.CSS_SELECTOR, args[0]):
                label.displayed = False
        elif len(args) == 2:
            field, value = args
            assert isinstance(field, FakeElement) and isinstance(value, str)
            field.value = value
        else:
            element = args[0]
            assert isinstance(element, FakeElement)
            element.click()


class TypingUser:
    """Answers each code prompt from a list, as someone would from the interface."""

    def __init__(self, interaction: renfe.Interaction, codes: list[str]) -> None:
        self.interaction = interaction
        self.codes = codes
        self.prompts: list[str] = []

    def state(self, state: JobState, message: str) -> None:
        if state is JobState.AWAITING_CODE:
            self.prompts.append(message)
            self.interaction.code.submit(self.codes.pop(0))

    def log(self, message: str) -> None: ...
    def attempt(self, count: int) -> None: ...
    def trains(self, trains: list[renfe.Train]) -> None: ...


@pytest.fixture(autouse=True)
def no_poll_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(renfe, "LOGIN_POLL_INTERVAL", 0)


def log_in(driver: VerificationModal, codes: list[str]) -> TypingUser:
    interaction = renfe.Interaction()
    user = TypingUser(interaction, codes)
    renfe._await_session(driver, user, interaction)
    return user


def test_the_code_goes_through_the_validar_button() -> None:
    """Enter does nothing in Renfe's modal; only the button's handler sends the code."""
    driver = VerificationModal()

    user = log_in(driver, [VALID_CODE])

    assert driver.codes_checked == [VALID_CODE]
    assert driver.current_url == HOME_URL
    assert len(user.prompts) == 1


def test_a_rejected_code_asks_for_another() -> None:
    driver = VerificationModal()

    user = log_in(driver, ["111111", VALID_CODE])

    assert driver.codes_checked == ["111111", VALID_CODE]
    assert "no ha aceptado" in user.prompts[1]


def test_the_previous_rejection_is_not_read_as_the_next_verdict() -> None:
    """Without clearing it, the stale error answers for a code Renfe has not checked."""
    driver = VerificationModal()

    user = log_in(driver, ["111111", "222222", VALID_CODE])

    assert driver.codes_checked == ["111111", "222222", VALID_CODE]
    assert len(user.prompts) == 3


def test_running_out_of_attempts_requests_a_new_code() -> None:
    driver = VerificationModal(attempts_allowed=1)

    user = log_in(driver, ["111111", VALID_CODE])

    assert driver.regenerated == 1
    assert driver.codes_checked == ["111111", VALID_CODE]
    assert "código nuevo" in user.prompts[1]
