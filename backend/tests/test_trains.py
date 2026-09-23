import threading

import pytest
from fastapi.testclient import TestClient
from selenium.common.exceptions import TimeoutException

from app.bot import renfe
from app.bot.events import JobState

LISTED = [
    renfe.Train(departure="07:30", cells={"Salida": "07:30", "Llegada": "08:45"}),
    renfe.Train(departure="09:10", cells={"Salida": "09:10", "Llegada": "10:25"}),
]


class FakeCell:
    def __init__(self, label: str, text: str) -> None:
        self.attributes = {"data-label": label, "textContent": text}

    def get_attribute(self, name: str) -> str | None:
        return self.attributes.get(name)


class FakeRow:
    def __init__(self, **cells: str) -> None:
        self.cells = [FakeCell(label, text) for label, text in cells.items()]

    def find_elements(self, by: str, selector: str) -> list[FakeCell]:
        return self.cells


class TableDriver:
    def __init__(self, rows: list[FakeRow]) -> None:
        self.rows = rows

    def find_elements(self, by: str, selector: str) -> list[FakeRow]:
        return self.rows


def test_lists_each_train_with_every_column_renfe_shows() -> None:
    trains = renfe.list_trains(
        TableDriver([FakeRow(Salida="07:30", Llegada="08:45", Tren="MD 18045")])
    )
    assert trains == [
        {
            "departure": "07:30",
            "cells": {"Salida": "07:30", "Llegada": "08:45", "Tren": "MD 18045"},
        }
    ]


def test_departure_is_extracted_from_decorated_cell_text() -> None:
    trains = renfe.list_trains(TableDriver([FakeRow(Salida="\n  Salida  7:05 h\n")]))
    assert trains[0]["departure"] == "7:05"
    assert trains[0]["cells"]["Salida"] == "Salida 7:05 h"


def test_rows_without_a_departure_time_are_skipped() -> None:
    trains = renfe.list_trains(
        TableDriver([FakeRow(Salida="Sin horario"), FakeRow(Llegada="10:00")])
    )
    assert trains == []


def test_repeated_departures_are_offered_once() -> None:
    """Polling tells trains apart by departure alone, so a duplicate is unbookable."""
    trains = renfe.list_trains(
        TableDriver(
            [FakeRow(Salida="07:30", Tren="A"), FakeRow(Salida="07:30", Tren="B")]
        )
    )
    assert [t["cells"]["Tren"] for t in trains] == ["A"]


class ExpiringWait:
    def until(self, condition: object) -> None:
        raise TimeoutException("no results table")


class ReadyWait:
    def until(self, condition: object) -> object:
        return object()


class RecordingReporter:
    def __init__(self) -> None:
        self.states: list[JobState] = []
        self.listed: list[renfe.Train] = []
        self.on_state = lambda state: None

    def state(self, state: JobState, message: str) -> None:
        self.states.append(state)
        self.on_state(state)

    def log(self, message: str) -> None: ...
    def attempt(self, count: int) -> None: ...

    def trains(self, trains: list[renfe.Train]) -> None:
        self.listed = trains


def test_an_empty_results_page_fails_with_a_clear_message() -> None:
    with pytest.raises(renfe.NoTrainsListed, match="no ha devuelto trenes"):
        renfe._choose_train(
            TableDriver([]), ExpiringWait(), RecordingReporter(), renfe.Interaction()
        )


def test_a_client_answering_instantly_is_never_turned_away() -> None:
    """The prompt opens before the list is published, so no reply can arrive too soon."""
    interaction = renfe.Interaction()
    reporter = RecordingReporter()
    reporter.on_state = lambda state: (
        state == JobState.AWAITING_TRAIN and interaction.train.submit("09:10")
    )

    chosen = renfe._choose_train(
        TableDriver([FakeRow(Salida="07:30"), FakeRow(Salida="09:10")]),
        ReadyWait(),
        reporter,
        interaction,
    )

    assert chosen == "09:10"
    assert [t["departure"] for t in reporter.listed] == ["07:30", "09:10"]
    assert reporter.states == [JobState.AWAITING_TRAIN]


SEARCH = {"journey_type": "ida", "date": "01/10/2026"}


@pytest.fixture
def listing_job(client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch):
    """Starts a job that lists trains and records the one it is told to take."""
    asked, done = threading.Event(), threading.Event()
    chosen: list[str] = []

    def fake_run_search(request, reporter, interaction) -> None:
        interaction.train.request()
        reporter.trains(LISTED)
        reporter.state(JobState.AWAITING_TRAIN, "Elige uno de los 2 trenes del día.")
        asked.set()
        chosen.append(interaction.train.wait(interaction.cancel))
        done.set()
        interaction.release.wait(timeout=5)

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)
    started = client.post("/api/jobs/current", json={"user_id": profile["id"], **SEARCH})
    assert started.status_code == 202
    assert started.json()["search"]["departure_time"] is None
    assert asked.wait(timeout=5)

    yield chosen, done
    client.post("/api/jobs/current/stop")


def test_the_listed_trains_are_part_of_the_job_status(
    client: TestClient, listing_job: tuple
) -> None:
    status = client.get("/api/jobs/current").json()
    assert status["state"] == "awaiting_train"
    assert [t["departure"] for t in status["trains"]] == ["07:30", "09:10"]


def test_choosing_a_listed_train_sends_the_bot_after_it(
    client: TestClient, listing_job: tuple
) -> None:
    chosen, done = listing_job
    response = client.post("/api/jobs/current/train", json={"departure_time": "09:10"})

    assert response.status_code == 202
    assert done.wait(timeout=5)
    assert chosen == ["09:10"]
    assert client.get("/api/jobs/current").json()["search"]["departure_time"] == "09:10"


def test_a_train_that_was_not_listed_is_rejected(
    client: TestClient, listing_job: tuple
) -> None:
    response = client.post("/api/jobs/current/train", json={"departure_time": "23:59"})
    assert response.status_code == 422
    assert client.get("/api/jobs/current").json()["state"] == "awaiting_train"


def test_a_second_choice_is_rejected(client: TestClient, listing_job: tuple) -> None:
    _, done = listing_job
    client.post("/api/jobs/current/train", json={"departure_time": "07:30"})
    assert done.wait(timeout=5)

    second = client.post("/api/jobs/current/train", json={"departure_time": "09:10"})
    assert second.status_code == 409


def test_choosing_without_a_listing_conflicts(client: TestClient) -> None:
    response = client.post("/api/jobs/current/train", json={"departure_time": "07:30"})
    assert response.status_code == 409


@pytest.mark.parametrize("departure", ["7h30", "", "07:30:00"])
def test_malformed_choices_are_rejected(client: TestClient, departure: str) -> None:
    response = client.post("/api/jobs/current/train", json={"departure_time": departure})
    assert response.status_code == 422


def test_trains_and_choice_reach_the_client_but_not_the_log(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """They shape the status panel; replaying them as log lines would only add noise."""
    chosen = threading.Event()

    def fake_run_search(request, reporter, interaction) -> None:
        interaction.train.request()
        reporter.trains(LISTED)
        reporter.state(JobState.AWAITING_TRAIN, "Elige tren")
        interaction.train.wait(interaction.cancel)
        chosen.set()

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)

    with client.websocket_connect("/api/jobs/stream") as websocket:
        websocket.receive_json()
        client.post("/api/jobs/current", json={"user_id": profile["id"], **SEARCH})

        messages = []
        while not messages or messages[-1].get("state") != "awaiting_train":
            messages.append(websocket.receive_json())
        client.post("/api/jobs/current/train", json={"departure_time": "07:30"})
        while messages[-1]["type"] != "search":
            messages.append(websocket.receive_json())

    assert chosen.wait(timeout=5)
    types = [m["type"] for m in messages]
    assert types == ["snapshot", "trains", "state", "search"]
    assert messages[-1]["search"]["departure_time"] == "07:30"

    with client.websocket_connect("/api/jobs/stream") as websocket:
        replay = websocket.receive_json()
    assert {e["type"] for e in replay["events"]} <= {"state", "log", "attempt"}
    assert replay["status"]["search"]["departure_time"] == "07:30"


def test_a_search_can_still_start_with_a_known_departure(
    client: TestClient, profile: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[str | None] = []

    def fake_run_search(request, reporter, interaction) -> None:
        received.append(request.departure_time)

    monkeypatch.setattr("app.bot.runner.run_search", fake_run_search)
    response = client.post(
        "/api/jobs/current",
        json={"user_id": profile["id"], "departure_time": "07:30", **SEARCH},
    )
    assert response.status_code == 202
    assert response.json()["search"]["departure_time"] == "07:30"
