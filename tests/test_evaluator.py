from uuid import uuid4

import pytest

from substrate.model import Action, ActionType, Principal, Resource, ResourceType
from substrate.substrate import Substrate

from norma.tools.evaluator.evaluator import NormEvaluator
from norma.tools.evaluator.instance_store import NormInstanceStore
from norma.tools.evaluator.model import NormStatus
from norma.tools.evaluator.pattern_store import NormPatternStore


@pytest.fixture
def substrate():
    substrate = Substrate()
    substrate.state.principals.extend([Principal("p1"), Principal("p2")])
    substrate.state.resources.extend([Resource("dataset-1", ResourceType.DATASET)])
    return substrate


def test_pattern_store_round_trip():
    store = NormPatternStore()
    pattern_id = store.insert(
        "send_message",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: "message_id" in action.parameters,
        lambda action, state: False,
    )

    pattern = store.get(pattern_id)

    assert pattern is not None
    assert pattern.name == "send_message"
    assert len(store.get_all()) == 1


def test_instance_store_round_trip():
    store = NormInstanceStore()
    pattern_id = uuid4()

    instance_id = store.insert(pattern_id, "p1", object="p2", project_id="project-1")
    instance = store.get(instance_id)

    assert instance is not None
    assert instance.pattern_id == pattern_id
    assert instance.subject == "p1"
    assert instance.object == "p2"
    assert instance.project_id == "project-1"
    assert len(store.get_all()) == 1


def test_get_applicable_norms_includes_active_and_state_changed_instances(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()

    send_pattern_id = pattern_store.insert(
        "send_message",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: len(state.messages) >= 1,
        lambda action, state: False,
    )
    inactive_pattern_id = pattern_store.insert(
        "unused_pattern",
        lambda action, state: action.type == ActionType.USE,
        lambda action, state: False,
        lambda action, state: False,
    )

    send_instance_id = instance_store.insert(send_pattern_id, "p1", object="p2")
    instance_store.insert(inactive_pattern_id, "p1")

    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    action = Action(
        ActionType.SEND,
        "p1",
        {"message_id": "msg-1", "content": "hello", "recipient_id": "p2"},
    )

    applicable = evaluator.get_applicable_norms(action)

    assert [instance.id for instance in applicable] == [send_instance_id]


def test_evaluate_action_returns_discharged_status_for_matching_action(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()

    pattern_id = pattern_store.insert(
        "send_message_requires_record",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: "message_id" in action.parameters and len(state.messages) >= 1,
        lambda action, state: False,
    )
    instance_id = instance_store.insert(pattern_id, "p1", object="p2")

    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    action = Action(
        ActionType.SEND,
        "p1",
        {"message_id": "msg-1", "content": "hello", "recipient_id": "p2"},
    )

    result = evaluator.evaluate_action(action)

    assert result.action == action
    assert result.next_state is not substrate.state
    assert len(result.evaluations) == 1
    assert result.evaluations[0].instance_id == instance_id
    assert result.evaluations[0].status == NormStatus.DISCHARGED
    assert len(evaluator.history) == 1
    assert substrate.state.messages == []


def test_get_applicable_norms_raises_when_pattern_is_missing(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()
    instance_store.insert(uuid4(), "p1")

    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    action = Action(ActionType.USE, "p1", {"resource_id": "dataset-1"})

    with pytest.raises(ValueError, match="NormPattern with id"):
        evaluator.get_applicable_norms(action)


def test_norm_status_helpers_cover_inactive_and_violation_states(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()

    pattern_id = pattern_store.insert(
        "use_is_violating",
        lambda action, state: action.type == ActionType.USE,
        lambda action, state: False,
        lambda action, state: True,
    )
    instance_store.insert(pattern_id, "p1")

    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    action = Action(ActionType.USE, "p1", {"resource_id": "dataset-1"})

    assert evaluator._get_norm_status(pattern_store.get(pattern_id), action, substrate.state) == NormStatus.VIOLATED

    inactive_pattern_id = pattern_store.insert(
        "inactive_rule",
        lambda action, state: False,
        lambda action, state: False,
        lambda action, state: False,
    )
    inactive_pattern = pattern_store.get(inactive_pattern_id)

    assert evaluator._get_norm_status(inactive_pattern, action, substrate.state) == NormStatus.INACTIVE


def test_history_allows_discharge_after_multiple_steps(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()
    pattern_id = pattern_store.insert(
        "request_then_wait",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: action.type == ActionType.WAIT,
        lambda action, state: False,
    )
    instance_store.insert(pattern_id, "p1")
    evaluator = NormEvaluator(pattern_store, instance_store, substrate)

    send = Action(ActionType.SEND, "p1", {"message_id": "msg-1", "content": "ready", "recipient_id": "p2"})
    substrate.execute(send)
    evaluator.evaluate_executed_action(send, step=1)
    wait = Action(ActionType.WAIT, "p1", {})
    substrate.execute(wait)

    result = evaluator.evaluate_executed_action(wait, step=2)

    assert result.evaluations[0].status == NormStatus.DISCHARGED
    assert [entry.step for entry in evaluator.history] == [0, 1, 2]


def test_history_can_supply_prior_evidence_for_a_later_violation(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()
    pattern_id = pattern_store.insert(
        "message_then_wait_violation",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: False,
        lambda action, state: action.type == ActionType.WAIT and bool(state.messages),
    )
    instance_store.insert(pattern_id, "p1")
    evaluator = NormEvaluator(pattern_store, instance_store, substrate)

    send = Action(ActionType.SEND, "p1", {"message_id": "msg-1", "content": "ready", "recipient_id": "p2"})
    substrate.execute(send)
    evaluator.evaluate_executed_action(send, step=1)
    wait = Action(ActionType.WAIT, "p1", {})
    substrate.execute(wait)

    result = evaluator.evaluate_executed_action(wait, step=2)
    assert result.evaluations[0].status == NormStatus.VIOLATED


def test_history_supports_step_based_deadline_conditions(substrate):
    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()
    pattern_id = pattern_store.insert(
        "deadline_norm",
        lambda action, state: action.type == ActionType.SEND,
        lambda action, state: False,
        lambda action, state: action.type == ActionType.WAIT and evaluator.history[-1].step >= 2,
    )
    instance_store.insert(pattern_id, "p1")
    evaluator = NormEvaluator(pattern_store, instance_store, substrate)

    send = Action(ActionType.SEND, "p1", {"message_id": "msg-1", "content": "ready", "recipient_id": "p2"})
    substrate.execute(send)
    evaluator.evaluate_executed_action(send, step=1)
    evaluator.record_state(2)
    wait = Action(ActionType.WAIT, "p1", {})
    substrate.execute(wait)

    result = evaluator.evaluate_executed_action(wait, step=2)

    assert result.evaluations[0].status == NormStatus.VIOLATED
