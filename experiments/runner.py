from norma.agent import NormaAgent, StepResult
from norma.tools.evaluator import NormStatus
from substrate import ViolationEvent

from .model import ExperimentResult, Scenario


def run_experiment(
    scenario: Scenario,
    agent: NormaAgent,
    max_steps: int = 10,
) -> ExperimentResult:
    steps: list[StepResult] = []
    sanctions = []
    next_violation_id = 1
    arbiter_feedback = None

    for _ in range(max_steps):
        if scenario.goal_reached(agent.substrate.get_state()):
            break

        step = agent.step(
            goal=scenario.goal,
            sanctions=(
                scenario.org.get_possible_sanctions()
                if scenario.org is not None
                else scenario.sanctions
            ),
            arbiter_feedback=arbiter_feedback,
        )
        steps.append(step)
        arbiter_feedback = None if step.decision.approved else step.decision.rationale

        if (
            step.execution_result is not None
            and step.execution_result.success
            and scenario.evaluator is not None
            and scenario.org is not None
        ):
            evaluation = scenario.evaluator.evaluate_executed_action(step.proposal.action)
            for norm_evaluation in evaluation.evaluations:
                if norm_evaluation.status != NormStatus.VIOLATED:
                    continue
                violation = ViolationEvent(
                    violation_id=next_violation_id,
                    subject=norm_evaluation.subject,
                    object=norm_evaluation.object,
                    norm_id=norm_evaluation.norm_id,
                )
                next_violation_id += 1
                decision = scenario.org.respond(violation)
                if decision is not None:
                    agent.substrate.apply_sanction(decision)
                    sanctions.append(decision)

        if scenario.goal_reached(agent.substrate.get_state()):
            break

    return ExperimentResult(
        scenario=scenario,
        steps=steps,
        achieved=scenario.goal_reached(agent.substrate.get_state()),
        sanctions=sanctions,
    )
