from dataclasses import dataclass, field
from typing import Callable

from substrate import SubstrateState
from norma.org import OrgSelf
from norma.tools.evaluator import NormEvaluator


@dataclass
class Scenario:
    name: str
    goal: str
    sanctions: list[str]
    goal_reached: Callable[[SubstrateState], bool]
    evaluator: NormEvaluator | None = None
    org: OrgSelf | None = None


@dataclass
class ExperimentResult:
    scenario: Scenario
    steps: list
    achieved: bool
    sanctions: list = field(default_factory=list)
