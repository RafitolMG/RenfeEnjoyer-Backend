import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# Must be set before importing the app: config resolves the DB path at import time.
os.environ["RENFE_DB_PATH"] = str(Path(tempfile.gettempdir()) / "renfe_enjoyer_test.db")

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db.session import get_session
from app.main import app


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def profile(client: TestClient) -> dict:
    response = client.post(
        "/api/users",
        json={
            "username": "demo",
            "email": "demo@example.com",
            "password": "secreto",
            "abono": "ABONO123",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(autouse=True)
def reset_job_manager() -> Iterator[None]:
    """The manager is a process-wide singleton, so tests must not inherit its state."""
    from app.bot.runner import job_manager

    yield
    job_manager._job = None
    job_manager._history.clear()
