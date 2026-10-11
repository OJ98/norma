import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from norma.llm import LLM

from .message_logger import _json_value
from .model import ExperimentResult, GoalNormRelationship
from .run_scenarios import build
from .runner import run_experiment
from .scenarios import SCENARIOS, Spec, infer_metadata


RELATION_TYPES = tuple(GoalNormRelationship)


def _spec(name: str) -> Spec:
    spec = SCENARIOS[name]()
    if spec.metadata is None:
        spec.metadata = infer_metadata(name, spec)
    return spec


def sample_names(count: int = 4, seed: int = 0) -> list[str]:
    """Choose a reproducible sample with one scenario per relationship type."""
    if count < len(RELATION_TYPES):
        raise ValueError(f"num-scenarios must be at least {len(RELATION_TYPES)}")
    if count > len(SCENARIOS):
        raise ValueError(f"num-scenarios cannot exceed {len(SCENARIOS)}")

    by_type: dict[GoalNormRelationship | str, list[str]] = {}
    for name in SCENARIOS:
        relationship = _spec(name).metadata.goal_norm_relationship
        by_type.setdefault(relationship, []).append(name)

    missing = [relationship.value for relationship in RELATION_TYPES if not by_type.get(relationship)]
    if missing:
        raise ValueError(f"No scenarios available for type(s): {', '.join(missing)}")

    generator = random.Random(seed)
    selected = [generator.choice(by_type[relationship]) for relationship in RELATION_TYPES]
    selected_set = set(selected)
    remaining = [name for name in SCENARIOS if name not in selected_set]
    generator.shuffle(remaining)
    selected.extend(remaining[: count - len(selected)])
    generator.shuffle(selected)
    return selected


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _result_payload(result: ExperimentResult) -> dict[str, Any]:
    return {
        "status": "success" if result.achieved else "failure",
        "scenario_id": result.scenario.name,
        "scenario_type": _json_value(result.scenario.metadata.goal_norm_relationship),
        "achieved": result.achieved,
        "steps": _json_value(result.steps),
        "sanctions": _json_value(result.sanctions),
    }


def run_sample(
    count: int = 4,
    seed: int = 0,
    output_dir: str | Path = "experiments/results",
    llm: LLM | None = None,
    max_steps: int | None = None,
) -> list[dict[str, Any]]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    names = sample_names(count, seed)
    outcomes: list[dict[str, Any]] = []

    for index, name in enumerate(names, start=1):
        spec = _spec(name)
        scenario_type = _json_value(spec.metadata.goal_norm_relationship)
        print(f"[{index}/{len(names)}] starting {name} ({scenario_type})")
        result_path = output_path / f"{index:02d}-{_safe_name(name)}.json"
        log_path = output_path / f"{index:02d}-{_safe_name(name)}.log"
        try:
            scenario, agent, _ = build(name, spec, llm=llm, log_path=log_path)
            result = run_experiment(
                scenario,
                agent,
                max_steps=max_steps or spec.max_steps,
            )
            outcome = _result_payload(result)
        except Exception as error:
            outcome = {
                "status": "failure",
                "scenario_id": name,
                "scenario_type": scenario_type,
                "error": {"type": type(error).__name__, "message": str(error)},
            }
        result_path.write_text(json.dumps(outcome, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        outcomes.append(outcome)
        print(f"[{index}/{len(names)}] finished {name} ({scenario_type}): {outcome['status']}")

    succeeded = sum(outcome["status"] == "success" for outcome in outcomes)
    print(f"Summary: {succeeded}/{len(outcomes)} scenarios succeeded.")
    return outcomes


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run a reproducible sample of Norma scenarios.")
    parser.add_argument("--num-scenarios", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default="experiments/results")
    parser.add_argument("--max-steps", type=int)
    args = parser.parse_args()
    run_sample(
        count=args.num_scenarios,
        seed=args.seed,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
    )


if __name__ == "__main__":
    main()
