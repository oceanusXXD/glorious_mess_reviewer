"""Golden-sample recommendation and snapshot regression tests."""

import json
from pathlib import Path

import pytest

from tests.conftest import load_fixture

GOLDENS_DIR = Path(__file__).parent / "goldens"


def _load_golden_snapshot(name: str) -> dict[str, object]:
    return json.loads((GOLDENS_DIR / name).read_text(encoding="utf-8"))


def _normalize_review_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = json.loads(json.dumps(payload))
    normalized["created_at"] = "<normalized>"
    normalized["workflow_session_id"] = "<normalized>"
    return normalized


@pytest.mark.parametrize(
    ("fixture_name", "expected_recommendation", "score_floor", "score_ceiling"),
    [
        ("absurd_but_rigorous.json", "ADVANCE_TO_FULL_REVIEW", 4.0, 5.0),
        ("funny_but_hollow.json", "REJECT_AS_EMPTY_GIMMICK", 1.0, 3.5),
        ("serious_but_misfit.json", "REVISION_REQUIRED_BEFORE_REVIEW", 2.5, 4.0),
    ],
)
def test_golden_manuscript_recommendations(
    client,
    fixture_name: str,
    expected_recommendation: str,
    score_floor: float,
    score_ceiling: float,
) -> None:
    response = client.post("/review", json=load_fixture(fixture_name))
    assert response.status_code == 200
    body = response.json()
    assert body["final_recommendation"] == expected_recommendation
    assert score_floor <= body["final_score"] <= score_ceiling


@pytest.mark.parametrize(
    ("fixture_name", "golden_name"),
    [
        ("absurd_but_rigorous.json", "review_output_snapshots.json"),
        ("funny_but_hollow.json", "review_output_snapshots.json"),
        ("serious_but_misfit.json", "review_output_snapshots.json"),
    ],
)
def test_golden_manuscript_full_output_snapshots(client, fixture_name: str, golden_name: str) -> None:
    response = client.post("/review", json=load_fixture(fixture_name))
    assert response.status_code == 200

    expected = _load_golden_snapshot(golden_name)[fixture_name]
    assert _normalize_review_payload(response.json()) == expected
