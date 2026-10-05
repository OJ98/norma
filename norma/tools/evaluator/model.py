from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeAlias
from uuid import UUID

from substrate import Action, SubstrateState

# Predicates remain small functions over one action and one state. Temporal
# predicates can use NormEvaluator.history_matches when prior steps matter.
Predicate: TypeAlias = Callable[[Action, SubstrateState], bool]

class NormStatus(Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    DISCHARGED = "discharged"
    VIOLATED = "violated"

@dataclass
class NormPattern:
    # A pattern defines the rule; it does not identify the participants or
    # resource involved in a particular scenario.
    id: UUID
    name: str
    antecedent: Predicate
    discharge_condition: Predicate
    violation_condition: Predicate


@dataclass
class NormInstance:
    # An instance binds a pattern to a subject and optional object/project.
    id: UUID
    pattern_id: UUID
    subject: str
    object: str | None = None
    project_id: str | None = None


@dataclass
class NormEvaluation:
    instance_id: int
    status: NormStatus
    norm_id: str | None = None
    subject: str | None = None
    object: str | None = None

@dataclass
class EvaluationResult:
    action: Action
    next_state: SubstrateState
    evaluations: list[NormEvaluation]


@dataclass(frozen=True)
class HistoryEntry:
    # State-only entries represent world events; action entries represent
    # successful agent executions observed by the evaluator.
    step: int
    state: SubstrateState
    action: Action | None = None
