"""EvidenceSludgeEngine: extracts claims, structure, and checkable support."""

from glorious_mess_reviewer.agents.base import BaseReviewAgent
from glorious_mess_reviewer.schemas import EvidenceAgentOutput


class EvidenceSludgeEngineAgent(BaseReviewAgent[EvidenceAgentOutput]):
    """Evidence agent that scores argument clarity, reasoning, and payload."""

    agent_name = "EvidenceSludgeEngine"
    template_name = "evidence_agent.j2"
    response_model = EvidenceAgentOutput
