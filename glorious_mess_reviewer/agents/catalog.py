"""Registry-style definitions for the built-in screening agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from glorious_mess_reviewer.agents.absurdity_but_make_it_rigorous import (
    AbsurdityButMakeItRigorousAgent,
)
from glorious_mess_reviewer.agents.base import BaseReviewAgent
from glorious_mess_reviewer.agents.evidence_sludge_engine import EvidenceSludgeEngineAgent
from glorious_mess_reviewer.agents.final_sediment_council import FinalSedimentCouncilAgent
from glorious_mess_reviewer.agents.han_ce_gate import HanCeGateAgent
from glorious_mess_reviewer.providers import LLMProvider


@dataclass(frozen=True)
class ReviewAgentSpec:
    """Stable metadata for one review agent node."""

    node_id: str
    artifact_key: str
    description: str
    phase: str
    agent_cls: type[BaseReviewAgent[Any]]

    @property
    def agent_name(self) -> str:
        """Expose the runtime-visible agent name."""

        return self.agent_cls.agent_name


class ScreeningAgentCatalog:
    """Construct and expose the built-in screening agents as a small registry."""

    DEFAULT_SPECS: tuple[ReviewAgentSpec, ...] = (
        ReviewAgentSpec(
            node_id="precheck.llm",
            artifact_key="precheck.llm",
            description="LLM precheck that enriches the deterministic intake verdict.",
            phase="precheck",
            agent_cls=HanCeGateAgent,
        ),
        ReviewAgentSpec(
            node_id="panel.evidence",
            artifact_key="panel.evidence",
            description="Evidence-focused panel agent for claims, reasoning, and payload.",
            phase="panel",
            agent_cls=EvidenceSludgeEngineAgent,
        ),
        ReviewAgentSpec(
            node_id="panel.value",
            artifact_key="panel.value",
            description="Value-focused panel agent for venue fit and absurd originality.",
            phase="panel",
            agent_cls=AbsurdityButMakeItRigorousAgent,
        ),
        ReviewAgentSpec(
            node_id="panel.meta",
            artifact_key="panel.meta",
            description="Meta panel that aggregates surviving upstream panel outputs.",
            phase="aggregation",
            agent_cls=FinalSedimentCouncilAgent,
        ),
    )

    def __init__(self, provider: LLMProvider | None, *, prompt_version: str = "v1") -> None:
        self._specs = {spec.node_id: spec for spec in self.DEFAULT_SPECS}
        self._agents = {
            spec.node_id: spec.agent_cls(provider, prompt_version=prompt_version)
            for spec in self.DEFAULT_SPECS
        }

    def spec(self, node_id: str) -> ReviewAgentSpec:
        """Return metadata for one registered node."""

        return self._specs[node_id]

    def agent(self, node_id: str) -> BaseReviewAgent[Any]:
        """Return the instantiated agent for one registered node."""

        return self._agents[node_id]

    def specs(self) -> tuple[ReviewAgentSpec, ...]:
        """Return all registered specs in declaration order."""

        return self.DEFAULT_SPECS

    def list_node_ids(self) -> list[str]:
        """List workflow node identifiers for all registered agents."""

        return [spec.node_id for spec in self.DEFAULT_SPECS]

    @property
    def precheck_agent(self) -> HanCeGateAgent:
        """Return the registered precheck agent instance."""

        return self._agents["precheck.llm"]  # type: ignore[return-value]

    @property
    def evidence_agent(self) -> EvidenceSludgeEngineAgent:
        """Return the registered evidence agent instance."""

        return self._agents["panel.evidence"]  # type: ignore[return-value]

    @property
    def value_agent(self) -> AbsurdityButMakeItRigorousAgent:
        """Return the registered value agent instance."""

        return self._agents["panel.value"]  # type: ignore[return-value]

    @property
    def meta_agent(self) -> FinalSedimentCouncilAgent:
        """Return the registered meta agent instance."""

        return self._agents["panel.meta"]  # type: ignore[return-value]
