"""Agent catalog coverage for the built-in screening workflow."""

from glorious_mess_reviewer.agents import ScreeningAgentCatalog


def test_screening_agent_catalog_exposes_expected_nodes_and_metadata() -> None:
    catalog = ScreeningAgentCatalog(provider=None)

    assert catalog.list_node_ids() == [
        "precheck.llm",
        "panel.evidence",
        "panel.value",
        "panel.meta",
    ]
    assert catalog.spec("precheck.llm").agent_name == "HanCeGateAgent"
    assert catalog.spec("panel.meta").artifact_key == "panel.meta"
    assert catalog.spec("panel.value").phase == "panel"
