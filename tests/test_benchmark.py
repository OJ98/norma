from collections import Counter

from experiments.model import GoalNormRelationship
from experiments.scenarios import BENCHMARK_SCENARIO_NAMES, SCENARIOS
from experiments.validate_benchmark import validate


def test_benchmark_uses_three_balanced_relationships():
    counts = Counter(
        SCENARIOS[name]().metadata.goal_norm_relationship
        for name in BENCHMARK_SCENARIO_NAMES
    )

    assert len(BENCHMARK_SCENARIO_NAMES) == 259
    assert counts == {
        GoalNormRelationship.ALIGNED: 87,
        GoalNormRelationship.VIOLATION_ATTRACTIVE: 86,
        GoalNormRelationship.VIOLATION_UNHELPFUL: 86,
    }


def test_benchmark_static_validator_accepts_all_variants(tmp_path):
    report, status = validate(tmp_path / "benchmark-validation.json")

    assert status == 0
    assert report["total_variants"] == 259
    assert report["passed"] == 259
    assert report["failed"] == 0
    assert report["behaviorally_validated"] is False
