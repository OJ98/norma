from dataclasses import dataclass

from substrate import Substrate, ActionResult

from norma.arbiter import Arbiter, ArbiterDecision
from norma.reasoner import Reasoner, ReasonerProposal

@dataclass
class StepResult:
    proposal: ReasonerProposal
    decision: ArbiterDecision
    execution_result: ActionResult | None

class NormaAgent:
    def __init__(self, reasoner: Reasoner, arbiter: Arbiter, substrate: Substrate):
        self.reasoner = reasoner
        self.arbiter = arbiter
        self.substrate = substrate

    def step(self, goal:str, sanctions: list[str] | str, arbiter_feedback: str | None = None) -> StepResult:
        state = self.substrate.get_state()
        proposal = self.reasoner.propose(goal=goal, state=state, sanctions=sanctions, arbiter_feedback=arbiter_feedback)

        decision = self.arbiter.review(goal=goal,proposal=proposal, state=state, sanctions=sanctions)
        execution = None

        if decision.approved:
            execution = self.substrate.execute(proposal.action)

        return StepResult(proposal=proposal, decision=decision, execution_result=execution)