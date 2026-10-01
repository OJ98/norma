from substrate import Substrate, Action, SubstrateState

from .model import NormEvaluation, NormPattern, NormInstance, NormStatus, EvaluationResult

from .pattern_store import NormPatternStore
from .instance_store import NormInstanceStore

class NormEvaluator:
    def __init__(self, pattern_store: NormPatternStore, instance_store: NormInstanceStore, substrate: Substrate):
        self.pattern_store = pattern_store
        self.instance_store = instance_store
        self.substrate = substrate

    def get_applicable_norms(self, action: Action) -> list[NormInstance]:
        applicable_norms = []
        instances = self.instance_store.get_all()
        for instance in instances:
            try:
                pattern = self.pattern_store.get(instance.pattern_id)
            except KeyError as exc:
                raise ValueError(f"NormPattern with id {instance.pattern_id} not found in store.") from exc
            current_state = self.substrate.get_state()
            next_state = self.substrate.simulate_action(action)
            current_status = self._get_norm_status(pattern, action, current_state)
            next_status = self._get_norm_status(pattern, action, next_state)
            if(current_status == NormStatus.ACTIVE or current_status != next_status):
                applicable_norms.append(instance)
        return applicable_norms

    def evaluate_action(self, action: Action) -> EvaluationResult:
        evaluations = []

        state: SubstrateState = self.substrate.get_state()
        next_state:SubstrateState = self.substrate.simulate_action(action)
        
        applicable_norms = self.get_applicable_norms(action)

        for instance in applicable_norms:
            # Extract the pattern from the store using the pattern_id of the instance
            try:
                pattern = self.pattern_store.get(instance.pattern_id)
            except KeyError as exc:
                raise ValueError(f"NormPattern with id {instance.pattern_id} not found in store.") from exc
            status = self._get_norm_status(pattern, action, next_state)
            evaluations.append(NormEvaluation(instance_id=instance.id, status=status))
        return EvaluationResult(action=action, next_state=next_state, evaluations=evaluations)

    def _get_norm_status(self, pattern: NormPattern, action: Action, state: SubstrateState) -> NormStatus:
        if not pattern.antecedent(action, state):
            return NormStatus.INACTIVE
        if pattern.violation_condition(action, state):
            return NormStatus.VIOLATED
        if pattern.discharge_condition(action, state):
            return NormStatus.DISCHARGED
        return NormStatus.ACTIVE