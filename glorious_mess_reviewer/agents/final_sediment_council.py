"""FinalSedimentCouncil: merges subreviews into a unified meta review."""

from glorious_mess_reviewer.agents.base import BaseReviewAgent
from glorious_mess_reviewer.schemas import FinalMetaReviewOutput


class FinalSedimentCouncilAgent(BaseReviewAgent[FinalMetaReviewOutput]):
    """Meta-review agent that produces unified scores and rationale."""

    agent_name = "FinalSedimentCouncil"
    template_name = "meta_agent.j2"
    response_model = FinalMetaReviewOutput
