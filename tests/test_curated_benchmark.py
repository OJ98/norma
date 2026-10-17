from experiments.scenarios import (
    CURATED_BENCHMARK_VERSION,
    CURATED_RECORDS,
    load_curated_scenarios,
    select_curated_scenarios,
    validate_curated_records,
)


def test_curated_dataset_is_exactly_55_valid_records():
    assert CURATED_BENCHMARK_VERSION == "1.0.0"
    assert len(CURATED_RECORDS) == 55
    assert validate_curated_records() == []
    assert len({record.scenario_id for record in CURATED_RECORDS}) == 55


def test_curated_loader_materializes_explicit_metadata():
    scenarios = load_curated_scenarios()

    assert set(scenarios) == {record.scenario_id for record in CURATED_RECORDS}
    assert all(spec.metadata.scenario_id for spec in scenarios.values())
    assert all(spec.metadata.success_condition for spec in scenarios.values())
    assert any(spec.metadata.norm_cardinality == "single" for spec in scenarios.values())
    assert any(spec.metadata.norm_cardinality == "multi" for spec in scenarios.values())


def test_curated_sampling_is_deterministic_and_definition_preserving():
    first = select_curated_scenarios(seed=7, limit=8)
    second = select_curated_scenarios(seed=7, limit=8)

    assert first == second
    assert len(first) == 8
    assert len(set(first)) == 8
