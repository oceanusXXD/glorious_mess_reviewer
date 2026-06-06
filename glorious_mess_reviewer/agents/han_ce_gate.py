"""HanCeGateAgent: serious precheck with a playful name."""

from glorious_mess_reviewer.agents.base import BaseReviewAgent
from glorious_mess_reviewer.schemas import PrecheckOutput


class HanCeGateAgent(BaseReviewAgent[PrecheckOutput]):
    """Precheck agent that decides whether a manuscript can enter full review."""

    agent_name = "HanCeGateAgent"
    template_name = "precheck_agent.j2"
    response_model = PrecheckOutput
