from dataclasses import dataclass
from enum import Enum
from typing import Callable, TypeAlias
from uuid import UUID

from substrate import Action, SubstrateState

Predicate: TypeAlias = Callable[[Action, SubstrateState], bool]

class NormStatus(Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    DISCHARGED = "discharged"
    VIOLATED = "violated"

@dataclass
class NormPattern:
    id: UUID
    name: str
    antecedent: Predicate
    discharge_condition: Predicate
    violation_condition: Predicate


@dataclass
class NormInstance:
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
