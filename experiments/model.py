from dataclasses import dataclass, field
from typing import Callable

from substrate import Substrate, SubstrateState
from norma.org import OrgSelf
from norma.tools.evaluator import NormEvaluator


@dataclass
class Scenario:
    # `goal_reached` should inspect the complete state, including prerequisite
    # actions, rather than only the most recent agent action.
    name: str
    goal: str
    sanctions: list[str]
    goal_reached: Callable[[SubstrateState], bool]
    # The evaluator and Org are optional so a scenario can focus on mechanics
    # without enabling normative evaluation or sanctions.
    evaluator: NormEvaluator | None = None
    org: OrgSelf | None = None
    # Events are keyed by logical step and receive the shared mutable substrate.
    world_events: dict[int, list[Callable[[Substrate], None]]] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    scenario: Scenario
    steps: list
    achieved: bool
    sanctions: list = field(default_factory=list)
