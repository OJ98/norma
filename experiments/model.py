from dataclasses import dataclass
from typing import Callable

from substrate import SubstrateState


@dataclass
class Scenario:
    name: str
    goal: str
    sanctions: list[str]
    goal_reached: Callable[[SubstrateState], bool]


@dataclass
class ExperimentResult:
    scenario: Scenario
    steps: list
    achieved: bool
