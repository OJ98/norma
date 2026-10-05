from copy import deepcopy

from substrate import Substrate, Action, SubstrateState

from .model import EvaluationResult, HistoryEntry, NormEvaluation, NormInstance, NormPattern, NormStatus

from .pattern_store import NormPatternStore
from .instance_store import NormInstanceStore

class NormEvaluator:
    def __init__(self, pattern_store: NormPatternStore, instance_store: NormInstanceStore, substrate: Substrate):
        self.pattern_store = pattern_store
        self.instance_store = instance_store
        self.substrate = substrate
        self.history: list[HistoryEntry] = [
            HistoryEntry(step=0, state=deepcopy(substrate.get_state()))
        ]

    def record_state(self, step: int) -> None:
        # Capture a copy so later substrate mutations cannot rewrite history.
        self.history.append(HistoryEntry(step=step, state=deepcopy(self.substrate.get_state())))

    def record_action(self, action: Action, step: int) -> None:
        self.history.append(
            HistoryEntry(step=step, action=action, state=deepcopy(self.substrate.get_state()))
        )

    def history_matches(self, predicate) -> bool:
        # History predicates inspect only entries that represent an action;
        # state-only world-event snapshots remain available through `history`.
        return any(
            entry.action is not None and predicate(entry.action, entry.state)
            for entry in self.history
        )

    def get_applicable_norms(
        self,
        action: Action,
        current_state: SubstrateState | None = None,
        next_state: SubstrateState | None = None,
    ) -> list[NormInstance]:
        # Simulate the candidate once, then reuse that projected state for every
        # norm to keep evaluation isolated without repeating the copy.
        applicable_norms = []
        instances = self.instance_store.get_all()
        current_state = current_state or self.substrate.get_state()
        next_state = next_state or self.substrate.simulate_action(action)
        for instance in instances:
            try:
                pattern = self.pattern_store.get(instance.pattern_id)
            except KeyError as exc:
                raise ValueError(f"NormPattern with id {instance.pattern_id} not found in store.") from exc
            current_applicable = pattern.antecedent(action, current_state)
            next_applicable = pattern.antecedent(action, next_state)
            if current_applicable or next_applicable or self.history_matches(pattern.antecedent):
                applicable_norms.append(instance)
        return applicable_norms

    def evaluate_action(self, action: Action) -> EvaluationResult:
        # This is a proposal-time, read-only assessment. It does not append to
        # history because the action may still be rejected by the Arbiter.
        evaluations = []

        state: SubstrateState = self.substrate.get_state()
        next_state:SubstrateState = self.substrate.simulate_action(action)
        
        applicable_norms = self.get_applicable_norms(action, state, next_state)

        for instance in applicable_norms:
            # Extract the pattern from the store using the pattern_id of the instance
            try:
                pattern = self.pattern_store.get(instance.pattern_id)
            except KeyError as exc:
                raise ValueError(f"NormPattern with id {instance.pattern_id} not found in store.") from exc
            status = self._get_norm_status(pattern, action, next_state)
            evaluations.append(
                NormEvaluation(
                    instance_id=instance.id,
                    status=status,
                    norm_id=pattern.name,
                    subject=instance.subject,
                    object=instance.object,
                )
            )
        return EvaluationResult(
            action=action,
            next_state=next_state,
            evaluations=evaluations,
        )

    def evaluate_executed_action(self, action: Action, step: int | None = None) -> EvaluationResult:
        # The runner calls this after execution, which makes the action eligible
        # for later temporal conditions.
        state = self.substrate.get_state()
        evaluations = []

        for instance in self.instance_store.get_all():
            pattern = self.pattern_store.get(instance.pattern_id)
            status = self._get_norm_status(pattern, action, state)
            evaluations.append(
                NormEvaluation(
                    instance_id=instance.id,
                    status=status,
                    norm_id=pattern.name,
                    subject=instance.subject,
                    object=instance.object,
                )
            )

        self.record_action(action, step=step if step is not None else self.history[-1].step + 1)

        return EvaluationResult(
            action=action,
            next_state=state,
            evaluations=evaluations,
        )

    def _get_norm_status(self, pattern: NormPattern, action: Action, state: SubstrateState) -> NormStatus:
        if not (
            pattern.antecedent(action, state)
            or self.history_matches(pattern.antecedent)
        ):
            return NormStatus.INACTIVE
        if pattern.violation_condition(action, state) or self.history_matches(pattern.violation_condition):
            return NormStatus.VIOLATED
        if pattern.discharge_condition(action, state) or self.history_matches(pattern.discharge_condition):
            return NormStatus.DISCHARGED
        return NormStatus.ACTIVE