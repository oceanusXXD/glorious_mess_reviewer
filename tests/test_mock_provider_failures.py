"""Mock-provider failure and degradation tests."""

import pytest

from glorious_mess_reviewer.providers import MockLLMProvider, ProviderError
from glorious_mess_reviewer.schemas import EvidenceAgentOutput
from tests.conftest import load_fixture


@pytest.mark.asyncio
async def test_mock_provider_rejects_invalid_json_payload(mock_registry) -> None:
    registry = dict(mock_registry)
    registry[("absurd-rigorous-001", "EvidenceSludgeEngine")] = "not-json"
    provider = MockLLMProvider(registry)
    with pytest.raises(ProviderError):
        await provider.complete_json(
            task_name="EvidenceSludgeEngine",
            prompt="x",
            response_model=EvidenceAgentOutput,
            metadata={"manuscript_id": "absurd-rigorous-001"},
        )


@pytest.mark.asyncio
async def test_mock_provider_rejects_schema_missing_fields(mock_registry) -> None:
    registry = dict(mock_registry)
    registry[("absurd-rigorous-001", "EvidenceSludgeEngine")] = {"paper_summary": "missing the rest"}
    provider = MockLLMProvider(registry)
    with pytest.raises(ProviderError):
        await provider.complete_json(
            task_name="EvidenceSludgeEngine",
            prompt="x",
            response_model=EvidenceAgentOutput,
            metadata={"manuscript_id": "absurd-rigorous-001"},
        )


def test_review_degrades_when_mock_payload_is_schema_invalid(settings, mock_registry) -> None:
    from fastapi.testclient import TestClient

    from glorious_mess_reviewer.api import create_app
    from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
    from glorious_mess_reviewer.storage import SQLiteReviewStore

    registry = dict(mock_registry)
    registry[("partial-failure-004", "EvidenceSludgeEngine")] = {"paper_summary": "bad payload only"}
    app = create_app(
        settings=settings,
        orchestrator=ReviewOrchestrator(
            settings=settings,
            provider=MockLLMProvider(registry),
            store=SQLiteReviewStore(settings.database_path),
        ),
    )
    response = TestClient(app).post("/review", json=load_fixture("partial_failure.json"))
    assert response.status_code == 200
    assert response.json()["agent_failures"]
