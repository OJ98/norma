from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from substrate import Substrate, SubstrateState
from norma.org import OrgSelf
from norma.tools.evaluator import NormEvaluator


class ScenarioTier(str, Enum):
    NORM_RECOGNITION = "norm-recognition"
    GOAL_NORM_DELIBERATION = "goal-norm-deliberation"
    NORM_INTERACTION = "norm-interaction"


@dataclass
class ScenarioMetadata:
    scenario_id: str = ""
    template: str = ""
    tier: ScenarioTier | str = ScenarioTier.NORM_RECOGNITION
    category: str = ""
    domain: str = ""
    norm_ids: list[str] = field(default_factory=list)
    norm_cardinality: str = ""
    sanction_types: list[str] = field(default_factory=list)
    goal_norm_relationship: str = "aligned"  # aligned, delayed, or conflict
    compliance_goal_outcome: str = "achieved"
    violation_goal_outcome: str = "achieved"
    violation_sanction: str = ""
    norm_count: int = 0
    tags: list[str] = field(default_factory=list)
    goal_variation: str | None = None
    state_variation: str | None = None
    description: str = ""
    success_condition: str = ""
    step_limit: int | None = None


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
    metadata: ScenarioMetadata | None = None


@dataclass
class ExperimentResult:
    scenario: Scenario
    steps: list
    achieved: bool
    sanctions: list = field(default_factory=list)
