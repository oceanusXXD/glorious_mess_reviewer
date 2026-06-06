"""AbsurdityButMakeItRigorous: judges whether the zhenghuo actually lands."""

from glorious_mess_reviewer.agents.base import BaseReviewAgent
from glorious_mess_reviewer.schemas import ValueAgentOutput


class AbsurdityButMakeItRigorousAgent(BaseReviewAgent[ValueAgentOutput]):
    """Value agent that scores venue fit, originality, and meme-to-argument quality."""

    agent_name = "AbsurdityButMakeItRigorous"
    template_name = "value_agent.j2"
    response_model = ValueAgentOutput
