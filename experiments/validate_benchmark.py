"""Validate deterministic benchmark construction, not scenario behavior.

The checks below mirror ``_parameterize_benchmark_spec`` in scenarios.py.
They verify that generated variants retain their base template and that the
declared relationship selected the expected deterministic transformation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if "--curated" in sys.argv:
    os.environ["NORMA_CURATED_MODE"] = "1"

from .model import GoalNormRelationship
from .scenarios import BENCHMARK_SCENARIO_NAMES, SCENARIOS
from substrate import Principal, Substrate
from .curated_benchmark import (
    CURATED_BENCHMARK_VERSION,
    CURATED_RECORDS,
    VALID_CARDINALITIES,
    VALID_DOMAINS,
    load_curated_scenarios,
    validate_curated_records,
)
from .scenarios import SANCTIONS


RELATIONSHIPS = tuple(GoalNormRelationship)
VARIANT_NAME = re.compile(r"^benchmark-(?P<index>\d{3})-(?P<relationship>.+)$")


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _expected_transformation(relation: GoalNormRelationship) -> dict[str, Any]:
    """Return the construction contract for one relationship."""
    if relation == GoalNormRelationship.ALIGNED:
        return {
            "world": "baseline-world",
            "event_shift": 0,
            "max_step_delta": 0,
            "compliance_step_delta": 0,
            "compliance_outcome": "achieved",
            "violation_outcome": "achieved",
            "violation_steps": "baseline",
        }
    if relation == GoalNormRelationship.VIOLATION_ATTRACTIVE:
        return {
            "world": "compressed-deadline",
            "event_shift": 0,
            "max_step_delta": -1,
            "compliance_step_delta": 0,
            "compliance_outcome": "achieved",
            "violation_outcome": "achieved",
            "violation_steps": "baseline-minus-one",
        }
    if relation == GoalNormRelationship.VIOLATION_UNHELPFUL:
        return {
            "world": "blocked-violation-world",
            "event_shift": 2,
            "max_step_delta": 2,
            "compliance_step_delta": 2,
            "compliance_outcome": "achieved",
            "violation_outcome": "failed",
            "violation_steps": None,
        }
    raise ValueError(f"Unsupported relationship: {relation!r}")


def _check(result: dict[str, Any], condition: bool, message: str) -> None:
    passed = bool(condition)
    result["checks"].append({"check": message, "passed": passed})
    if not passed:
        result["mismatches"].append(message)


def validate_variant(name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scenario_name": name,
        "base_template": None,
        "expected_relationship": None,
        "checks": [],
        "passed": True,
        "mismatches": [],
    }

    match = VARIANT_NAME.fullmatch(name)
    _check(result, match is not None, "name contains a benchmark index and relationship")
    if match is None:
        result["passed"] = False
        return result

    index = int(match.group("index"))
    spec = SCENARIOS[name]()
    metadata = spec.metadata
    result["base_template"] = metadata.template if metadata else None
    result["expected_relationship"] = _value(metadata.goal_norm_relationship) if metadata else None

    relation = _value(metadata.goal_norm_relationship) if metadata else None
    supported = relation in {item.value for item in RELATIONSHIPS}
    _check(result, supported, "metadata relationship is supported")
    if not supported:
        result["passed"] = False
        return result

    relation_enum = GoalNormRelationship(relation)
    rules = _expected_transformation(relation_enum)
    base_name = metadata.template
    base_registered = base_name in SCENARIOS and "benchmark-variant" not in SCENARIOS[base_name]().tags
    _check(result, base_registered, "metadata template is a registered base scenario")
    if not base_registered:
        result["passed"] = False
        return result

    base_spec = SCENARIOS[base_name]()
    base_metadata = base_spec.metadata
    _check(result, match.group("relationship") == relation, "name relationship matches metadata relationship")
    _check(result, index == int(metadata.state_variation.rsplit("-", 1)[-1]), "variant index matches state variation")
    _check(result, f"variant {index:03d}" in metadata.description, "variant index is recorded in description")
    _check(result, base_metadata.template == base_name, "base template metadata is self-consistent")
    _check(result, spec.metadata.norm_ids == base_metadata.norm_ids, "variant preserves base norm identifiers")
    _check(result, spec.metadata.norm_count == base_metadata.norm_count, "variant preserves base norm count")
    _check(result, spec.metadata.compliance_goal_outcome == rules["compliance_outcome"], "compliance outcome matches relationship")
    _check(result, spec.metadata.violation_goal_outcome == rules["violation_outcome"], "violation outcome matches relationship")

    base_steps = base_spec.max_steps
    _check(result, spec.max_steps == base_steps + rules["max_step_delta"], "max_steps has the expected relationship delta")
    expected_keys = {max(1, step + rules["event_shift"]) for step in base_spec.world_events}
    _check(result, set(spec.world_events) == expected_keys, "world event steps have the expected shift")
    _check(result, spec.tags.intersection({rules["world"]}), "implementation tag matches relationship")

    paths = spec.counterfactual_paths
    _check(result, set(paths) == {"compliance", "violation"}, "counterfactual paths contain both declared paths")
    if set(paths) == {"compliance", "violation"}:
        _check(result, paths["compliance"]["outcome"] == metadata.compliance_goal_outcome, "compliance path matches metadata")
        _check(result, paths["violation"]["outcome"] == metadata.violation_goal_outcome, "violation path matches metadata")
        expected_compliance_steps = base_steps + rules["compliance_step_delta"]
        expected_violation_steps = rules["violation_steps"]
        if expected_violation_steps == "baseline":
            expected_violation_steps = base_steps
        elif expected_violation_steps == "baseline-minus-one":
            expected_violation_steps = max(1, base_steps - 1)
        _check(result, paths["compliance"]["steps"] == expected_compliance_steps, "compliance path steps match construction")
        _check(result, paths["violation"]["steps"] == expected_violation_steps, "violation path steps match construction")
        _check(result, paths["compliance"]["world"] == rules["world"], "compliance path world matches construction")
        _check(result, paths["violation"]["world"] == rules["world"], "violation path world matches construction")
        _check(result, paths["violation"].get("sanction") == metadata.violation_sanction, "violation path sanction matches metadata")

    result["passed"] = not result["mismatches"]
    return result


def validate(output_path: str | Path | None = None) -> tuple[dict[str, Any], int]:
    results = [validate_variant(name) for name in BENCHMARK_SCENARIO_NAMES]
    by_expected = Counter(result["expected_relationship"] for result in results)
    by_status = Counter("passed" if result["passed"] else "failed" for result in results)
    report = {
        "validator": "deterministic benchmark construction validator",
        "behaviorally_validated": False,
        "total_variants": len(results),
        "passed": by_status["passed"],
        "failed": by_status["failed"],
        "counts_by_relationship": dict(sorted(by_expected.items(), key=lambda item: str(item[0]))),
        "counts_by_status": dict(by_status),
        "failed_scenarios": [result["scenario_name"] for result in results if not result["passed"]],
        "results": results,
    }
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        output_path = Path("experiments/logs") / f"benchmark_validation_{timestamp}.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, 0 if report["failed"] == 0 else 1


def validate_curated(output_path: str | Path | None = None) -> tuple[dict[str, Any], int]:
    errors = validate_curated_records()
    records = {record.scenario_id: record for record in CURATED_RECORDS}
    try:
        specs = load_curated_scenarios()
    except (TypeError, ValueError, KeyError) as exc:
        errors.append(f"loader failed: {exc}")
        specs = {}

    norm_names = {
        "N0": "request_before_use", "N1": "resource_prioritization",
        "N2": "resource_modification", "N3": "resource_access",
        "N4": "irb_compliance", "N5": "ai_use_disclosure",
        "N6": "unanimity", "N7": "majority", "N8": "idle_allocation",
        "N9": "group_storage", "N10": "fault_reporting", "N11": "login_node",
        "N12": "blind_review", "N13": "gift_authorship",
        "N14": "review_confidentiality", "N15": "published_dataset",
        "N16": "dual_submission", "N17": "conflict_of_interest",
        "N18": "account_sharing", "N19": "gpu_hogging", "N20": "gpu_squatting",
    }
    for scenario_id, record in records.items():
        spec = specs.get(scenario_id)
        if spec is None:
            continue
        actual_norms = {norm_names[norm_id] for norm_id in record.norm_ids}
        declared_norms = {norm[0] for norm in spec.norms}
        if actual_norms != declared_norms:
            errors.append(f"{scenario_id}: metadata norms do not match the spec")
        if not spec.metadata.success_condition:
            errors.append(f"{scenario_id}: missing success condition")
        if spec.metadata.norm_count != len(record.norm_ids):
            errors.append(f"{scenario_id}: inconsistent norm count")
        if spec.metadata.domain not in VALID_DOMAINS:
            errors.append(f"{scenario_id}: invalid domain")
        if spec.metadata.norm_cardinality not in VALID_CARDINALITIES:
            errors.append(f"{scenario_id}: invalid norm cardinality")
        expected_sanctions = [
            SANCTIONS[norm_names[norm_id]].value for norm_id in record.norm_ids
        ]
        if spec.metadata.sanction_types != expected_sanctions:
            errors.append(f"{scenario_id}: sanction metadata does not match policy")
        try:
            state = Substrate()
            state.state.principals.extend(Principal(principal) for principal in spec.principals)
            state.state.resources.extend(spec.resources)
            state.state.projects.extend(spec.projects)
            state.state.resource_requests.extend(spec.requests)
            state.state.messages.extend(spec.messages)
            spec.goal_reached(state.get_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"{scenario_id}: success condition cannot inspect initial state: {exc}")

    report = {
        "validator": "curated benchmark validator",
        "dataset_version": CURATED_BENCHMARK_VERSION,
        "total_scenarios": len(CURATED_RECORDS),
        "passed": not errors,
        "errors": errors,
        "scenario_ids": [record.scenario_id for record in CURATED_RECORDS],
    }
    if output_path is None:
        output_path = Path("experiments/logs") / "curated_benchmark_validation.json"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic benchmark construction.")
    parser.add_argument("--output", type=Path, help="JSON report path (default: experiments/logs/...)")
    parser.add_argument("--curated", action="store_true", help="validate the frozen 50-scenario dataset")
    args = parser.parse_args()
    report, status = validate_curated(args.output) if args.curated else validate(args.output)
    if args.curated:
        print(f"Dataset version: {report['dataset_version']}")
        print(f"Total scenarios: {report['total_scenarios']}")
        print(f"Passed: {report['passed']}")
        print(f"Errors: {report['errors']}")
    else:
        print(f"Total variants: {report['total_variants']}")
        print(f"Passed: {report['passed']}")
        print(f"Failed: {report['failed']}")
        print(f"Counts by relationship: {report['counts_by_relationship']}")
        print(f"Failed scenarios: {report['failed_scenarios']}")
    return status


if __name__ == "__main__":
    sys.exit(main())
