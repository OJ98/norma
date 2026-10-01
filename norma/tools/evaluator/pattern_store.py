from uuid import UUID, uuid4

from .model import NormPattern, Predicate

class NormPatternStore:
    def __init__(self):
        self._patterns: dict[UUID, NormPattern] = {}

    def insert(self, name:str, antecedent: Predicate, discharge_condition: Predicate, violation_condition: Predicate) -> None:
        pattern = NormPattern(
            id=uuid4(),
            name=name,
            antecedent=antecedent,
            discharge_condition=discharge_condition,
            violation_condition=violation_condition,
        )
        self._patterns[pattern.id] = pattern
        return pattern.id

    def get(self, pattern_id: UUID) -> NormPattern | None:
        try:
            return self._patterns[pattern_id]
        except KeyError:
            raise KeyError(f"NormPattern with id {pattern_id} not found in store.") from None

    def get_all(self) -> list[NormPattern]:
        return list(self._patterns.values())