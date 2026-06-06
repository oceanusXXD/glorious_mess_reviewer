"""Shared test fixtures for app creation and deterministic provider setup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from glorious_mess_reviewer.api import create_app
from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.providers import MockLLMProvider
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.mock_fixtures import build_mock_registry


def load_fixture(name: str) -> dict[str, object]:
    """Load a JSON manuscript fixture."""

    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def mock_registry() -> dict[tuple[str, str], dict[str, object] | str]:
    return build_mock_registry()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        provider_backend="mock",
        database_path=tmp_path / "reviews.db",
        minimum_reviewable_characters=200,
        store_raw_agent_outputs=True,
    )


@pytest.fixture
def orchestrator(settings: Settings, mock_registry) -> ReviewOrchestrator:
    return ReviewOrchestrator(
        settings=settings,
        provider=MockLLMProvider(mock_registry),
        store=SQLiteReviewStore(settings.database_path),
    )


@pytest.fixture
def client(settings: Settings, orchestrator: ReviewOrchestrator) -> TestClient:
    app = create_app(settings=settings, orchestrator=orchestrator)
    return TestClient(app)
