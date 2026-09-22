import threading
from dataclasses import dataclass
from typing import Protocol

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.bot.driver import build_chrome_driver
from app.bot.events import JobState
from app.config import SELENIUM_TIMEOUT

# loginParticular accepts an email in the `num_tarjeta` field (labelled
# "Email / Número Más Renfe"). loginCEX is the company login and takes a client
# number instead, so it will not work with these credentials.
LOGIN_URL = "https://venta.renfe.com/vol/loginParticular.do?Idioma=es&Pais=ES"
PASSES_URL = "https://venta.renfe.com/vol/myPassesCard.do"
HOME_URL_FRAGMENT = "venta.renfe.com/vol/home.do"

JOURNEY_RADIO_IDS = {"ida": "journeyStationOrigin", "vuelta": "journeyStationDestin"}

CONFIRMATION_LOCATOR = (
    By.CSS_SELECTOR,
    ".paso4-enviar-billetes-passbook-boton-texto.semibold",
)

COOKIE_BANNER_TIMEOUT = 20
COOKIE_OVERLAY_LOCATOR = (By.ID, "onetrust-banner-sdk")
COOKIE_OVERLAY_TIMEOUT = 10
POLL_INTERVAL = 2.0
MODAL_SETTLE_DELAY = 2.0

# Renfe's login inputs accept focus before their scripts finish binding, so the first
# keystrokes are silently dropped. Each field is filled, read back and retried.
FIELD_FILL_ATTEMPTS = 4
FIELD_RETRY_DELAY = 0.5


class JobCancelled(Exception):
    """Raised when the user stops a running search."""


class LoginFailed(Exception):
    """Raised when the Renfe login does not complete."""


class Reporter(Protocol):
    def state(self, state: JobState, message: str) -> None: ...
    def log(self, message: str) -> None: ...
    def attempt(self, count: int) -> None: ...


@dataclass(frozen=True)
class SearchRequest:
    departure_time: str
    journey_type: str
    date: str
    email: str
    password: str
    abono: str


def run_search(
    request: SearchRequest,
    reporter: Reporter,
    cancel: threading.Event,
    release: threading.Event,
) -> None:
    """Drive a full booking attempt, blocking until the user releases the browser.

    Runs on a worker thread. `cancel` aborts at the next checkpoint; `release` signals
    that the user has finished the purchase and the browser may be closed.
    """
    if request.journey_type not in JOURNEY_RADIO_IDS:
        raise ValueError(f"Invalid journey type: {request.journey_type!r}")

    reporter.state(JobState.STARTING, "Abriendo el navegador")
    driver = build_chrome_driver()
    try:
        wait = WebDriverWait(driver, SELENIUM_TIMEOUT)
        _login(driver, wait, request, reporter, cancel)
        _guard(cancel)
        _open_pass(driver, wait, request, reporter)
        _guard(cancel)
        _submit_search(driver, wait, request, reporter)
        _poll_for_seat(driver, wait, request, reporter, cancel)

        reporter.state(
            JobState.RESERVED,
            "Plaza reservada. Completa la compra en la ventana del navegador.",
        )
        _await_release(release, cancel)
    finally:
        driver.quit()


def _login(
    driver: WebDriver,
    wait: WebDriverWait,
    request: SearchRequest,
    reporter: Reporter,
    cancel: threading.Event,
) -> None:
    reporter.state(JobState.LOGGING_IN, "Iniciando sesión en Renfe")
    driver.get(LOGIN_URL)
    _dismiss_cookie_banner(driver, reporter)

    fill_field(driver, wait, "num_tarjeta", request.email, cancel)
    fill_field(driver, wait, "pass-login", request.password, cancel)

    _click(driver, wait.until(EC.element_to_be_clickable((By.ID, "loginButtonId"))))
    try:
        wait.until(EC.url_contains(HOME_URL_FRAGMENT))
    except TimeoutException:
        raise LoginFailed(_login_failure_reason(driver)) from None
    reporter.log("Sesión iniciada")


def fill_field(
    driver: WebDriver,
    wait: WebDriverWait,
    field_id: str,
    value: str,
    cancel: threading.Event,
) -> None:
    """Fill an input and confirm the value landed, retrying until it does.

    `send_keys` reports success even when the page swallows the keystrokes, which is why
    the value is read back. The scripted fallback assigns through the native setter and
    replays the input events, so framework-bound fields still register the change.
    """
    for attempt in range(1, FIELD_FILL_ATTEMPTS + 1):
        try:
            field = wait.until(EC.element_to_be_clickable((By.ID, field_id)))
            field.click()
            field.clear()
            field.send_keys(value)
            if field.get_attribute("value") == value:
                return

            _assign_value_by_script(driver, field, value)
            if field.get_attribute("value") == value:
                return
        except (StaleElementReferenceException, ElementNotInteractableException):
            pass  # the form re-rendered underneath us; refetch on the next pass

        if attempt < FIELD_FILL_ATTEMPTS:
            _sleep(FIELD_RETRY_DELAY, cancel)

    # The value is never interpolated: one of these fields holds the password.
    raise LoginFailed(f"No se pudo rellenar el campo '{field_id}' del formulario")


def _assign_value_by_script(driver: WebDriver, field: WebElement, value: str) -> None:
    driver.execute_script(
        """
        const [field, value] = arguments;
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        setter.call(field, value);
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        field,
        value,
    )


def _login_failure_reason(driver: WebDriver) -> str:
    if "loginParticular" in driver.current_url:
        return (
            "No se completó el inicio de sesión. Revisa las credenciales, o resuelve "
            "el captcha o la verificación en la ventana del navegador."
        )
    return "No se completó el inicio de sesión."


def _dismiss_cookie_banner(driver: WebDriver, reporter: Reporter) -> None:
    try:
        banner = WebDriverWait(driver, COOKIE_BANNER_TIMEOUT).until(
            EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler"))
        )
    except TimeoutException:
        return
    _click(driver, banner)

    # The banner fades out; keystrokes sent while it still covers the form are lost.
    try:
        WebDriverWait(driver, COOKIE_OVERLAY_TIMEOUT).until(
            EC.invisibility_of_element_located(COOKIE_OVERLAY_LOCATOR)
        )
    except TimeoutException:
        reporter.log("El aviso de cookies no terminó de cerrarse; se continúa igualmente")


def _open_pass(
    driver: WebDriver, wait: WebDriverWait, request: SearchRequest, reporter: Reporter
) -> None:
    reporter.state(JobState.OPENING_PASS, f"Abriendo el abono {request.abono}")
    driver.get(PASSES_URL)

    # The pass button id is "new<abono>" right-padded with spaces, so match the prefix.
    locator = (By.XPATH, f"//*[starts-with(@id, 'new{request.abono}')]")
    _js_click(driver, wait.until(EC.visibility_of_element_located(locator)))
    wait.until(EC.element_to_be_clickable((By.ID, JOURNEY_RADIO_IDS["ida"])))


def _submit_search(
    driver: WebDriver, wait: WebDriverWait, request: SearchRequest, reporter: Reporter
) -> None:
    reporter.state(JobState.SEARCHING, "Configurando la búsqueda")
    radio = driver.find_element(By.ID, JOURNEY_RADIO_IDS[request.journey_type])
    _js_click(driver, radio)

    date_field = wait.until(EC.element_to_be_clickable((By.ID, "fecha1")))
    date_field.clear()
    date_field.send_keys(request.date)

    _js_click(driver, driver.find_element(By.ID, "submitSiguiente"))


def _poll_for_seat(
    driver: WebDriver,
    wait: WebDriverWait,
    request: SearchRequest,
    reporter: Reporter,
    cancel: threading.Event,
) -> None:
    reporter.state(JobState.POLLING, f"Buscando plazas para las {request.departure_time}")
    row_xpath = (
        f"//td[@data-label='Salida' and contains(text(), '{request.departure_time}')]"
        "/ancestor::tr"
    )

    attempt = 0
    while True:
        _sleep(POLL_INTERVAL, cancel)
        attempt += 1
        reporter.attempt(attempt)

        try:
            row = driver.find_element(By.XPATH, row_xpath)
            # Rows are identified as "row<n>"; the reserve button is "continuar<n>".
            row_number = (row.get_attribute("id") or "")[3:]
            _js_click(driver, driver.find_element(By.ID, f"continuar{row_number}"))

            submit = wait.until(EC.element_to_be_clickable((By.ID, "submitSiguiente")))
            _js_click(driver, submit)

            if _is_sold_out(driver, cancel):
                reporter.log(f"Intento {attempt}: sin asientos libres, recargando")
                driver.refresh()
                continue

            wait.until(EC.visibility_of_element_located(CONFIRMATION_LOCATOR))
            reporter.log(f"Plaza encontrada en el intento {attempt}")
            return
        except (NoSuchElementException, TimeoutException):
            reporter.log(f"Intento {attempt}: tren no disponible, recargando")
            driver.refresh()


def _is_sold_out(driver: WebDriver, cancel: threading.Event) -> bool:
    """Renfe raises a generic modal when the train fills up before reserving."""
    _sleep(MODAL_SETTLE_DELAY, cancel)
    try:
        return driver.find_element(By.ID, "modalGeneric").is_displayed()
    except NoSuchElementException:
        return False


def _click(driver: WebDriver, element: WebElement) -> None:
    """Click natively, falling back to JS when something covers the target.

    `element_to_be_clickable` only checks that an element is visible and enabled, not
    that it is on top. Renfe's cookie banner sits over its own reject button often
    enough that the native click is intercepted.
    """
    try:
        element.click()
    except ElementClickInterceptedException:
        _js_click(driver, element)


def _js_click(driver: WebDriver, element: WebElement) -> None:
    """Renfe's sticky overlays intercept native clicks, so dispatch through JS."""
    driver.execute_script("arguments[0].click();", element)


def _guard(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise JobCancelled


def _sleep(seconds: float, cancel: threading.Event) -> None:
    """Interruptible sleep so a stop request is not delayed by the poll interval."""
    if cancel.wait(seconds):
        raise JobCancelled


def _await_release(release: threading.Event, cancel: threading.Event) -> None:
    while not release.is_set():
        _sleep(0.5, cancel)
