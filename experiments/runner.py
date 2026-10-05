from norma.agent import NormaAgent, StepResult
from norma.tools.evaluator import NormStatus
from substrate import ViolationEvent, normalize_action_type

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
    current_step = 0

    if scenario.org is not None:
        scenario.org.clock = lambda: current_step

    if scenario.goal_reached(agent.substrate.get_state()):
        return ExperimentResult(
            scenario=scenario,
            steps=steps,
            achieved=True,
            sanctions=sanctions,
        )

    for current_step in range(1, max_steps + 1):
        # World events happen first, making independent approvals or agreements
        # visible to the agent and evaluator during this logical step.
        for event in scenario.world_events.get(current_step, []):
            event(agent.substrate)
        if scenario.evaluator is not None:
            scenario.evaluator.record_state(current_step)

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

        # Norms are checked only after a successful execution, so sanctions are
        # based on what actually changed the substrate rather than a proposal.
        if (
            step.execution_result is not None
            and step.execution_result.success
            and scenario.evaluator is not None
            and scenario.org is not None
        ):
            evaluation = scenario.evaluator.evaluate_executed_action(step.proposal.action, step=current_step)
            for norm_evaluation in evaluation.evaluations:
                if norm_evaluation.status != NormStatus.VIOLATED:
                    continue
                violation = ViolationEvent(
                    violation_id=next_violation_id,
                    subject=norm_evaluation.subject,
                    object=norm_evaluation.object,
                    norm_id=norm_evaluation.norm_id,
                    event_type=str(normalize_action_type(step.proposal.action.type).value),
                    timestamp=current_step,
                )
                next_violation_id += 1
                decisions = scenario.org.respond_all(violation)
                for decision in decisions:
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
