from norma.agent import NormaAgent, StepResult

from .model import ExperimentResult, Scenario


def run_experiment(
    scenario: Scenario,
    agent: NormaAgent,
    max_steps: int = 10,
) -> ExperimentResult:
    steps: list[StepResult] = []
    arbiter_feedback = None

    for _ in range(max_steps):
        if scenario.goal_reached(agent.substrate.get_state()):
            break

        step = agent.step(
            goal=scenario.goal,
            sanctions=scenario.sanctions,
            arbiter_feedback=arbiter_feedback,
        )
        steps.append(step)
        arbiter_feedback = None if step.decision.approved else step.decision.rationale

        if scenario.goal_reached(agent.substrate.get_state()):
            break

    return ExperimentResult(
        scenario=scenario,
        steps=steps,
        achieved=scenario.goal_reached(agent.substrate.get_state()),
    )
