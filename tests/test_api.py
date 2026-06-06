"""API integration tests."""

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from glorious_mess_reviewer.api import create_app
from glorious_mess_reviewer.config import Settings
from glorious_mess_reviewer.orchestrator import ReviewOrchestrator
from glorious_mess_reviewer.providers import MockLLMProvider
from glorious_mess_reviewer.storage import SQLiteReviewStore
from tests.conftest import load_fixture


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "glorious_mess_reviewer"
    assert body["provider_backend"] == "mock"
    assert body["default_model"] == "gpt-4o-mini"
    assert body["database_ok"] is True
    assert body["provider_configured"] is True


def test_review_success_path(client) -> None:
    response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert response.status_code == 200
    body = response.json()
    assert body["final_recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    assert body["final_score"] >= 4.0
    assert body["workflow_session_id"]
    assert "Screening decision:" in body["human_readable_review"]


def test_review_success_path_persists_workflow_session(client, settings) -> None:
    response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))

    assert response.status_code == 200
    with sqlite3.connect(settings.database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.review.v1", "completed")


def test_get_review_route_returns_persisted_review_record(client) -> None:
    create_response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert create_response.status_code == 200
    run_id = client.app.state.orchestrator._store.list_reviews(limit=1)[0].run_id

    response = client.get(f"/review/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["review"]["manuscript_id"] == "absurd-rigorous-001"
    assert body["request_payload"]["manuscript_id"] == "absurd-rigorous-001"


def test_get_review_display_route_returns_dashboard_projection(client) -> None:
    manuscript = load_fixture("absurd_but_rigorous.json")
    manuscript["metadata"] = {
        "ai_use_statement": "No generated text was used beyond copy editing.",
        "safety_notice": "No operational harm instructions or personal data are included.",
    }
    create_response = client.post("/review", json=manuscript)
    assert create_response.status_code == 200
    run_id = client.app.state.orchestrator._store.list_reviews(limit=1)[0].run_id

    response = client.get(f"/review/{run_id}/display")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["manuscript_id"] == "absurd-rigorous-001"
    assert body["recommendation"] == "ADVANCE_TO_FULL_REVIEW"
    assert body["suggested_stage"] == "real_shit_candidate"
    assert body["weighted_confidence"] == 0.86
    assert body["calibration_status"] == "high_confidence"
    assert body["triage"]["queue_priority"] == 10
    assert body["triage"]["lane"] == "ready_for_next_stage"
    assert body["triage"]["primary_revision"] == "Clarify the observational protocol."
    assert body["triage"]["action"] == "Advance to full review; carry the first revision into the next-stage brief."
    assert body["gates"][0] == {"name": "risk_flags", "status": "pass", "detail": "none"}
    gates = {gate["name"]: gate for gate in body["gates"]}
    assert gates["format_compliance"]["status"] == "pass"
    assert gates["citation_traceability"]["detail"] == "2 reference(s) supplied"
    assert gates["ai_disclosure_integrity"]["status"] == "pass"
    assert gates["safety_notice_presence"]["status"] == "pass"
    assert body["score_matrix"][0]["dimension"] == "venue_fit"
    assert body["score_matrix"][0]["evidence"] == ["panel evidence (manuscript)"]
    assert [group["group_id"] for group in body["score_groups"]] == [
        "structure_and_evidence",
        "zhenghuo_conversion",
        "community_signal",
    ]
    assert body["score_groups"][0]["mean_score"] == 4.67
    assert body["score_groups"][0]["mean_confidence"] == 0.86
    assert body["score_groups"][0]["status"] == "strong"
    assert body["score_groups"][0]["weakest_dimension"] == "method_or_reasoning_legibility"
    assert body["score_groups"][0]["weakest_score"] == 4
    assert body["score_groups"][0]["recommended_action"] == "Preserve the current structure and evidence trail."
    assert body["repair_targets"][0]["dimension"] == "method_or_reasoning_legibility"
    assert body["repair_targets"][0]["issue"] == "polish"
    assert body["repair_targets"][0]["priority_score"] == 1.1
    assert body["repair_targets"][0]["action"] == (
        "Polish method_or_reasoning_legibility; it is close but still below the top band."
    )
    assert "raw_agent_outputs" not in body


def test_get_review_display_route_prioritizes_weak_scores_before_readiness_metadata(client) -> None:
    create_response = client.post("/review", json=load_fixture("funny_but_hollow.json"))
    assert create_response.status_code == 200
    run_id = client.app.state.orchestrator._store.list_reviews(limit=1)[0].run_id

    response = client.get(f"/review/{run_id}/display")

    assert response.status_code == 200
    triage = response.json()["triage"]
    assert triage["queue_priority"] == 75
    assert triage["lane"] == "author_revision"
    assert triage["primary_score_group"] == "structure_and_evidence"
    assert triage["primary_gate"] is None
    assert triage["primary_revision"] == "Define a measurable task and gather evidence."
    assert triage["action"] == "Repair core_claim_clarity before asking for deeper review."
    repair_targets = response.json()["repair_targets"]
    assert [target["dimension"] for target in repair_targets[:2]] == ["result_payload", "core_claim_clarity"]
    assert repair_targets[0]["priority_score"] == 5.0
    assert repair_targets[0]["issue"] == "low_score"
    assert repair_targets[0]["action"] == (
        "Turn the premise into a payload: result, observation, artifact, or reusable insight."
    )


def test_get_review_route_returns_404_for_unknown_run(client) -> None:
    response = client.get("/review/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error_code"] == "review_not_found"


def test_get_review_display_route_returns_404_for_unknown_run(client) -> None:
    response = client.get("/review/does-not-exist/display")

    assert response.status_code == 404
    assert response.json()["error_code"] == "review_not_found"


def test_workflows_route_lists_registered_workflows(client) -> None:
    response = client.get("/workflows")

    assert response.status_code == 200
    body = response.json()
    workflow_ids = {item["workflow_id"] for item in body}
    assert "screening.review.v1" in workflow_ids
    assert "screening.risk_audit.v1" in workflow_ids
    assert "screening.venue_fit_audit.v1" in workflow_ids
    review_workflow = next(item for item in body if item["workflow_id"] == "screening.review.v1")
    assert ["panel.evidence", "panel.value"] in review_workflow["parallel_groups"]
    assert {
        (edge["source"], edge["target"], edge["condition"])
        for edge in review_workflow["edges"]
    } >= {
        ("precheck.llm", "panel.evidence", "reviewable_and_no_precheck_risk"),
        ("precheck.llm", "panel.value", "reviewable_and_no_precheck_risk"),
        ("precheck.llm", "projection.review", "precheck_blocked_or_risk_flagged"),
    }
    assert "decision.review_output" in review_workflow["artifact_keys"]


def test_workflow_sessions_route_lists_persisted_audit_sessions(client) -> None:
    client.post("/review/risk-audit", json=load_fixture("absurd_but_rigorous.json"))

    response = client.get(
        "/workflow-sessions",
        params={"workflow_id": "screening.risk_audit.v1", "manuscript_id": "absurd-rigorous-001"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["workflow_id"] == "screening.risk_audit.v1"
    assert body[0]["status"] == "completed"
    assert body[0]["manuscript_id"] == "absurd-rigorous-001"
    assert body[0]["final_output_type"] == "risk_audit_output"


def test_list_reviews_route_returns_summary_records(client) -> None:
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    client.post("/review", json=load_fixture("funny_but_hollow.json"))

    response = client.get("/reviews", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["run_id"]
    assert body[0]["manuscript_id"] == "funny-hollow-002"
    assert body[0]["resolved_venue_profile"]["preset_name"] == "shit-screening-default"


def test_list_reviews_route_can_filter_by_manuscript_id(client) -> None:
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    client.post("/review", json=load_fixture("funny_but_hollow.json"))

    response = client.get("/reviews", params={"manuscript_id": "absurd-rigorous-001", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["manuscript_id"] == "absurd-rigorous-001"


def test_list_review_display_route_returns_queue_summaries(client) -> None:
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    client.post("/review", json=load_fixture("funny_but_hollow.json"))

    response = client.get("/reviews/display", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["manuscript_id"] == "funny-hollow-002"
    assert body[0]["suggested_stage"] == "petri_dish_revision"
    assert body[0]["triage"]["lane"] == "author_revision"
    assert body[0]["triage"]["queue_priority"] == 75
    assert body[0]["top_repair_target"]["dimension"] == "result_payload"
    assert body[0]["needs_review_gates"] == ["ai_disclosure_integrity", "safety_notice_presence"]
    assert "score_matrix" not in body[0]


def test_list_review_display_route_can_filter_by_manuscript_id(client) -> None:
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    client.post("/review", json=load_fixture("funny_but_hollow.json"))

    response = client.get("/reviews/display", params={"manuscript_id": "absurd-rigorous-001", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["manuscript_id"] == "absurd-rigorous-001"
    assert body[0]["triage"]["lane"] == "submission_readiness"


def test_list_review_display_route_can_sort_and_filter_queue(client) -> None:
    risky = load_fixture("absurd_but_rigorous.json")
    risky["manuscript_id"] = "risk-sort-001"
    risky["abstract"] = "This draft repeatedly says it will weaponize office-chair logistics."
    client.post("/review", json=risky)
    client.post("/review", json=load_fixture("funny_but_hollow.json"))

    sorted_response = client.get("/reviews/display", params={"sort": "queue_priority", "limit": 10})

    assert sorted_response.status_code == 200
    sorted_body = sorted_response.json()
    assert sorted_body[0]["manuscript_id"] == "risk-sort-001"
    assert sorted_body[0]["triage"]["lane"] == "human_risk_review"
    assert sorted_body[0]["triage"]["queue_priority"] == 100

    filtered_response = client.get(
        "/reviews/display",
        params={"lane": "author_revision", "sort": "queue_priority", "limit": 10},
    )

    assert filtered_response.status_code == 200
    filtered_body = filtered_response.json()
    assert [item["manuscript_id"] for item in filtered_body] == ["funny-hollow-002"]


def test_list_review_display_route_can_sort_by_repair_priority(client) -> None:
    client.post("/review", json=load_fixture("funny_but_hollow.json"))
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))

    response = client.get("/reviews/display", params={"sort": "repair_priority", "limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert [item["manuscript_id"] for item in body] == ["funny-hollow-002", "absurd-rigorous-001"]
    assert body[0]["top_repair_target"]["dimension"] == "result_payload"
    assert body[0]["top_repair_target"]["priority_score"] > body[1]["top_repair_target"]["priority_score"]


def test_review_display_overview_route_returns_queue_counters(client) -> None:
    risky = load_fixture("absurd_but_rigorous.json")
    risky["manuscript_id"] = "risk-overview-001"
    risky["abstract"] = "This draft repeatedly says it will weaponize office-chair logistics."
    client.post("/review", json=risky)
    client.post("/review", json=load_fixture("funny_but_hollow.json"))
    client.post("/review", json=load_fixture("absurd_but_rigorous.json"))

    response = client.get("/reviews/display/overview", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["total_reviews"] == 3
    assert body["lane_counts"]["human_risk_review"] == 1
    assert body["lane_counts"]["author_revision"] == 1
    assert body["lane_counts"]["submission_readiness"] == 1
    assert body["needs_human_review"] == 1
    assert body["ready_for_next_stage"] == 0
    assert body["gate_counts"]["ai_disclosure_integrity"] == 3
    assert body["top_repair_hotspots"][0]["dimension"] == "result_payload"
    assert body["top_repair_hotspots"][0]["max_priority_score"] == 5.0


def test_health_endpoint_reports_degraded_provider_when_not_configured(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "health-no-provider.db",
    )

    response = TestClient(create_app(settings=settings)).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["database_ok"] is True
    assert body["provider_configured"] is False


def test_review_partial_agent_failure_path(settings, mock_registry) -> None:
    reduced_registry = dict(mock_registry)
    reduced_registry.pop(("partial-failure-004", "AbsurdityButMakeItRigorous"), None)
    reduced_registry.pop(("partial-failure-004", "FinalSedimentCouncil"), None)

    app = create_app(
        settings=settings,
        orchestrator=ReviewOrchestrator(
            settings=settings,
            provider=MockLLMProvider(reduced_registry),
            store=SQLiteReviewStore(settings.database_path),
        ),
    )
    response = TestClient(app).post("/review", json=load_fixture("partial_failure.json"))
    assert response.status_code == 200
    body = response.json()
    assert len(body["agent_failures"]) >= 1
    assert body["human_readable_review"]
    assert body["raw_agent_outputs"]["AbsurdityButMakeItRigorous"]["status"] == "failed"
    assert body["raw_agent_outputs"]["FinalSedimentCouncil"]["status"] == "fallback"


def test_review_escalates_when_only_downstream_agents_raise_risk_flags(settings, mock_registry) -> None:
    risky_registry = dict(mock_registry)
    risky_registry[("absurd-rigorous-001", "FinalSedimentCouncil")] = {
        **risky_registry[("absurd-rigorous-001", "FinalSedimentCouncil")],
        "risk_flags": ["risk_dangerous_actionable"],
    }

    app = create_app(
        settings=settings,
        orchestrator=ReviewOrchestrator(
            settings=settings,
            provider=MockLLMProvider(risky_registry),
            store=SQLiteReviewStore(settings.database_path),
        ),
    )

    response = TestClient(app).post("/review", json=load_fixture("absurd_but_rigorous.json"))

    assert response.status_code == 200
    body = response.json()
    assert body["final_recommendation"] == "ESCALATE_FOR_HUMAN_RISK_CHECK"
    assert "risk_dangerous_actionable" in body["risk_flags"]


def test_review_skips_downstream_panels_when_precheck_raises_risk(client) -> None:
    manuscript = load_fixture("absurd_but_rigorous.json")
    manuscript["abstract"] = "This draft teaches readers how to weaponize office chairs."

    response = client.post("/review", json=manuscript)

    assert response.status_code == 200
    body = response.json()
    assert body["final_recommendation"] == "ESCALATE_FOR_HUMAN_RISK_CHECK"
    assert "risk_dangerous_actionable" in body["risk_flags"]
    assert "EvidenceSludgeEngine" not in body["raw_agent_outputs"]
    assert "AbsurdityButMakeItRigorous" not in body["raw_agent_outputs"]
    assert body["raw_agent_outputs"]["HanCeGateAgent"]["status"] == "success"

    workflow = client.get(f"/workflow/{body['workflow_session_id']}").json()
    step_statuses = {step["node_id"]: step["status"] for step in workflow["steps"]}
    assert step_statuses["panel.evidence"] == "skipped"
    assert step_statuses["panel.value"] == "skipped"
    assert step_statuses["panel.meta"] == "skipped"
    skip_reasons = {
        step["node_id"]: step["details"]["reason"]
        for step in workflow["steps"]
        if step["status"] == "skipped"
    }
    assert skip_reasons["panel.evidence"] == "risk_gate"
    run_id = client.app.state.orchestrator._store.list_reviews(limit=1)[0].run_id
    display = client.get(f"/review/{run_id}/display").json()
    assert display["triage"]["queue_priority"] == 100
    assert display["triage"]["lane"] == "human_risk_review"
    assert display["triage"]["primary_gate"] == "risk_flags"


def test_review_exposes_stable_raw_agent_output_envelopes(client) -> None:
    response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert response.status_code == 200
    raw_outputs = response.json()["raw_agent_outputs"]
    assert raw_outputs["HanCeGateAgent"]["status"] == "success"
    assert raw_outputs["HanCeGateAgent"]["artifact_type"] == "precheck_output"
    assert "payload" in raw_outputs["HanCeGateAgent"]
    assert isinstance(raw_outputs["HanCeGateAgent"]["payload"]["notes"], list)
    assert raw_outputs["EvidenceSludgeEngine"]["status"] == "success"
    assert raw_outputs["EvidenceSludgeEngine"]["artifact_type"] == "evidence_output"
    assert raw_outputs["FinalSedimentCouncil"]["status"] == "success"
    assert raw_outputs["FinalSedimentCouncil"]["artifact_type"] == "meta_output"
    assert isinstance(
        raw_outputs["EvidenceSludgeEngine"]["payload"]["dimension_scores"]["core_claim_clarity"]["supporting_evidence"][0],
        dict,
    )


def test_review_failure_path_returns_422(client) -> None:
    response = client.post("/review", json={"title": "x"})
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_request"


def test_dry_run_path(client) -> None:
    manuscript = load_fixture("funny_but_hollow.json")
    manuscript["abstract"] = ""
    response = client.post("/review/dry-run", json=manuscript)
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_for_full_review"] is False
    assert "missing_abstract" in body["precheck"]["hard_failures"]


def test_dry_run_marks_risk_flagged_submission_as_not_ready(client) -> None:
    manuscript = {
        "manuscript_id": "risk-flag-dry-run-001",
        "title": "Weaponize the office gossip graph responsibly",
        "abstract": "This draft studies how rumor networks amplify harm while repeatedly using the word weaponize.",
        "body": "Conclusion\nLimitations\n" + ("This section warns readers not to weaponize social systems. " * 10),
    }

    response = client.post("/review/dry-run", json=manuscript)

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_for_full_review"] is False
    assert "risk_dangerous_actionable" in body["precheck"]["risk_flags"]


def test_dry_run_does_not_flag_cautionary_weaponize_mentions(client) -> None:
    manuscript = {
        "manuscript_id": "risk-cautionary-dry-run-001",
        "title": "A Safety Note on Office Metaphors",
        "abstract": "This draft warns readers not to weaponize social systems or workplace gossip.",
        "body": "Conclusion\nLimitations\n"
        + ("The paper studies language as a safety problem and says do not weaponize local coordination. " * 10),
    }

    response = client.post("/review/dry-run", json=manuscript)

    assert response.status_code == 200
    assert "risk_dangerous_actionable" not in response.json()["precheck"]["risk_flags"]


def test_dry_run_works_without_provider_configuration(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "no-provider.db",
        minimum_reviewable_characters=200,
    )
    app = create_app(settings=settings)
    response = TestClient(app).post("/review/dry-run", json=load_fixture("funny_but_hollow.json"))
    assert response.status_code == 200
    assert "precheck" in response.json()
    assert response.json()["manuscript_id"] == "funny-hollow-002"


def test_review_returns_structured_blocked_output_when_precheck_fails(client) -> None:
    manuscript = load_fixture("funny_but_hollow.json")
    manuscript["abstract"] = ""

    response = client.post("/review", json=manuscript)

    assert response.status_code == 200
    body = response.json()
    assert body["final_recommendation"] == "REVISION_REQUIRED_BEFORE_REVIEW"
    assert "missing_abstract" in body["hard_failures"]
    assert body["raw_agent_outputs"]["HanCeGateAgent"]["status"] == "success"
    assert body["paper_summary"].startswith("Precheck gated the pipeline")
    assert body["workflow_session_id"]


def test_workflow_route_returns_persisted_workflow_session(client) -> None:
    create_response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert create_response.status_code == 200
    session_id = create_response.json()["workflow_session_id"]

    response = client.get(f"/workflow/{session_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert body["workflow_id"] == "screening.review.v1"


def test_workflow_route_returns_404_for_unknown_session(client) -> None:
    response = client.get("/workflow/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error_code"] == "workflow_not_found"


def test_risk_audit_route_returns_typed_result_and_session(client, settings) -> None:
    payload = load_fixture("absurd_but_rigorous.json")
    payload["abstract"] = "This office-chair study keeps saying weaponize the workspace."

    response = client.post("/review/risk-audit", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_session_id"]
    assert body["action"] == "FLAG_FOR_HUMAN_REVIEW"
    assert "risk_dangerous_actionable" in body["risk_flags"]
    with sqlite3.connect(settings.database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.risk_audit.v1", "completed")


def test_venue_fit_audit_route_returns_typed_result_and_session(client, settings) -> None:
    response = client.post("/review/venue-fit-audit", json=load_fixture("absurd_but_rigorous.json"))

    assert response.status_code == 200
    body = response.json()
    assert body["workflow_session_id"]
    assert body["action"] == "STRONG_FIT"
    assert body["venue_fit_score"] >= 4
    with sqlite3.connect(settings.database_path) as connection:
        session_row = connection.execute(
            "SELECT workflow_id, status FROM workflow_sessions ORDER BY rowid DESC LIMIT 1"
        ).fetchone()

    assert session_row == ("screening.venue_fit_audit.v1", "completed")


def test_venue_fit_audit_requires_strong_zhenghuo_for_strong_fit(settings, mock_registry) -> None:
    registry = dict(mock_registry)
    value_payload = dict(registry[("absurd-rigorous-001", "AbsurdityButMakeItRigorous")])
    dimension_scores = dict(value_payload["dimension_scores"])
    dimension_scores["zhenghuo_execution"] = {
        **dimension_scores["zhenghuo_execution"],
        "score": 2,
        "reason": "The premise is superficially aligned but the bit does not actually land.",
    }
    value_payload["dimension_scores"] = dimension_scores
    registry[("absurd-rigorous-001", "AbsurdityButMakeItRigorous")] = value_payload
    app = create_app(
        settings=settings,
        orchestrator=ReviewOrchestrator(
            settings=settings,
            provider=MockLLMProvider(registry),
            store=SQLiteReviewStore(settings.database_path),
        ),
    )

    response = TestClient(app).post("/review/venue-fit-audit", json=load_fixture("absurd_but_rigorous.json"))

    assert response.status_code == 200
    body = response.json()
    assert body["venue_fit_score"] == 5
    assert body["meme_to_argument_score"] == 5
    assert body["zhenghuo_execution_score"] == 2
    assert body["action"] == "MISALIGNED"


def test_review_returns_502_when_provider_is_missing_even_for_blocked_manuscript(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "missing-provider-blocked.db",
        minimum_reviewable_characters=20,
    )
    app = create_app(settings=settings)
    manuscript = load_fixture("funny_but_hollow.json")
    manuscript["abstract"] = ""

    response = TestClient(app).post("/review", json=manuscript)

    assert response.status_code == 502
    assert response.json()["error_code"] == "provider_failure"


def test_venue_validate_path(client) -> None:
    response = client.post("/venue/validate", json=client.get("/venue/default").json())
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_default_venue_endpoint_returns_built_in_profile(client) -> None:
    response = client.get("/venue/default")
    assert response.status_code == 200
    body = response.json()
    assert body["venue_name"] == "S.H.I.T Initial Screening Desk"
    assert body["preset_name"] == "shit-screening-default"
    assert body["minimum_reviewable_characters"] == 200
    assert body["recommendation_policy"]["advance_to_full_review_min_final_score"] == 4.2


def test_default_venue_endpoint_can_return_named_preset(client) -> None:
    response = client.get("/venue/default", params={"preset": "shit-abstract-screening"})
    assert response.status_code == 200
    body = response.json()
    assert body["venue_name"] == "S.H.I.T Abstract Screening Track"
    assert body["preset_name"] == "shit-abstract-screening"


def test_review_returns_502_when_provider_is_missing_for_full_review(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="openai",
        openai_api_key=None,
        database_path=tmp_path / "missing-provider.db",
        minimum_reviewable_characters=20,
    )
    app = create_app(settings=settings)
    response = TestClient(app).post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert response.status_code == 502
    assert response.json()["error_code"] == "provider_failure"


def test_local_agent_bug_is_not_downgraded_into_graceful_fallback(settings, orchestrator) -> None:
    async def explode(*args, **kwargs):
        raise RuntimeError("local bug")

    orchestrator._evidence_agent.review = explode
    client = TestClient(
        create_app(settings=settings, orchestrator=orchestrator),
        raise_server_exceptions=False,
    )

    response = client.post("/review", json=load_fixture("absurd_but_rigorous.json"))

    assert response.status_code == 500
    assert response.json()["error_code"] == "internal_error"


def test_review_returns_clear_message_for_runtime_mock_backend_without_fixtures(tmp_path: Path) -> None:
    settings = Settings(
        provider_backend="mock",
        database_path=tmp_path / "runtime-mock.db",
        minimum_reviewable_characters=20,
    )
    app = create_app(settings=settings)
    response = TestClient(app).post("/review", json=load_fixture("absurd_but_rigorous.json"))
    assert response.status_code == 502
    assert "test-only" in response.json()["message"]
