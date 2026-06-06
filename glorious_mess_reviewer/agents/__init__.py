"""Subagent wrappers used by the review orchestrator."""

from glorious_mess_reviewer.agents.absurdity_but_make_it_rigorous import (
    AbsurdityButMakeItRigorousAgent,
)
from glorious_mess_reviewer.agents.catalog import ReviewAgentSpec, ScreeningAgentCatalog
from glorious_mess_reviewer.agents.evidence_sludge_engine import EvidenceSludgeEngineAgent
from glorious_mess_reviewer.agents.final_sediment_council import FinalSedimentCouncilAgent
from glorious_mess_reviewer.agents.han_ce_gate import HanCeGateAgent

__all__ = [
    "AbsurdityButMakeItRigorousAgent",
    "EvidenceSludgeEngineAgent",
    "FinalSedimentCouncilAgent",
    "HanCeGateAgent",
    "ReviewAgentSpec",
    "ScreeningAgentCatalog",
]
