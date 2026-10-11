import hashlib
import json

from norma.agent import NormaAgent, StepResult
from norma.tools.evaluator import NormStatus
from substrate import ViolationEvent, normalize_action_type, serialize_state

from .model import ExperimentResult, Scenario
from .message_logger import StructuredEventLogger, _json_value


def _state_snapshot(state) -> tuple[str, dict]:
    snapshot = json.loads(serialize_state(state))
    state_id = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return state_id, snapshot


def _logger(agent: NormaAgent) -> StructuredEventLogger | None:
    return getattr(getattr(agent.reasoner, "llm", None), "event_logger", None)


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
    event_logger = _logger(agent)
    scenario_metadata = scenario.metadata
    if event_logger is not None:
        event_logger.emit("RUN_STARTED", experiment=scenario.name, scenario_id=scenario.name)
        event_logger.emit(
            "SCENARIO_STARTED",
            scenario_id=scenario.name,
            goal=scenario.goal,
            applicable_norm_ids=(scenario_metadata.norm_ids if scenario_metadata else []),
            sanctions=scenario.org.get_possible_sanctions() if scenario.org else scenario.sanctions,
            success_condition=(
                scenario_metadata.success_condition
                if scenario_metadata and scenario_metadata.success_condition
                else "scenario.goal_reached(state)"
            ),
            step_limit=max_steps,
            tags=scenario_metadata.tags if scenario_metadata else [],
            tier=(scenario_metadata.tier if scenario_metadata else None),
        )

    if scenario.org is not None:
        scenario.org.clock = lambda: current_step

    if scenario.goal_reached(agent.substrate.get_state()):
        if event_logger is not None:
            event_logger.emit(
                "SCENARIO_COMPLETED",
                scenario_id=scenario.name,
                achieved=True,
                steps=0,
                goal_status={"achieved": True, "progress": 1.0},
            )
            event_logger.emit("RUN_COMPLETED", achieved=True)
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
        if event_logger is not None and scenario.world_events.get(current_step):
            state_id, snapshot = _state_snapshot(agent.substrate.get_state())
            event_logger.emit(
                "STATE_CHANGED",
                scenario_id=scenario.name,
                step=current_step,
                change_type="world_event",
                state_id=state_id,
                state_after=snapshot,
            )
        if scenario.evaluator is not None:
            scenario.evaluator.record_state(current_step)

        if scenario.goal_reached(agent.substrate.get_state()):
            break

        state_before_id, state_before = _state_snapshot(agent.substrate.get_state())
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
        action = step.proposal.action
        action_data = _json_value(action)
        if event_logger is not None:
            event_logger.emit(
                "REASONER_PROPOSED",
                scenario_id=scenario.name,
                step=current_step,
                state_id=state_before_id,
                proposed_action=action_data,
                rationale=step.proposal.rationale,
                candidate_actions=getattr(step.proposal, "candidate_actions", []),
            )
        if step.execution_result is not None:
            state_after_id, state_after = _state_snapshot(agent.substrate.get_state())
            if event_logger is not None:
                event_logger.emit(
                    "ACTION_EXECUTED",
                    scenario_id=scenario.name,
                    step=current_step,
                    action=action_data,
                    result=_json_value(step.execution_result),
                    state_before_id=state_before_id,
                    state_after_id=state_after_id,
                )
                event_logger.emit(
                    "STATE_CHANGED",
                    scenario_id=scenario.name,
                    step=current_step,
                    change_type="agent_action",
                    state_before_id=state_before_id,
                    state_after_id=state_after_id,
                    state_before=state_before,
                    state_after=state_after,
                )
        if event_logger is not None:
            event_logger.emit(
                "ARBITER_DECIDED",
                scenario_id=scenario.name,
                step=current_step,
                state_id=state_before_id,
                approved=step.decision.approved,
                rationale=step.decision.rationale,
                selected_action=action_data if step.decision.approved else None,
                executed=step.execution_result is not None,
            )
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
            evaluation_sanctions = []
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
                    evaluation_sanctions.append(decision)
                    if event_logger is not None:
                        event_logger.emit(
                            "SANCTION_APPLIED",
                            scenario_id=scenario.name,
                            step=current_step,
                            violation_id=decision.violation_id,
                            norm_id=norm_evaluation.norm_id,
                            sanction=decision,
                        )
            if event_logger is not None:
                event_logger.emit(
                    "NORM_EVALUATED",
                    scenario_id=scenario.name,
                    step=current_step,
                    phase="executed",
                    action=action_data,
                    evaluations=evaluation.evaluations,
                    applicable_norm_ids=[item.norm_id for item in evaluation.evaluations],
                    sanctions=evaluation_sanctions,
                )

        if scenario.goal_reached(agent.substrate.get_state()):
            break

    achieved = scenario.goal_reached(agent.substrate.get_state())
    if event_logger is not None:
        event_logger.emit(
            "SCENARIO_COMPLETED",
            scenario_id=scenario.name,
            achieved=achieved,
            steps=len(steps),
            goal_status={
                "achieved": achieved,
                "progress": 1.0 if achieved else 0.0,
                "actions": len(steps),
            },
        )
        event_logger.emit("RUN_COMPLETED", achieved=achieved)
    return ExperimentResult(
        scenario=scenario,
        steps=steps,
        achieved=achieved,
        sanctions=sanctions,
    )
