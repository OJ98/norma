# Commands (run from the repository root):
#   python -m experiments.run_scenarios --list                       list every scenario with its tags
#   python -m experiments.run_scenarios                              run all scenarios (21 singles + 12 combinations)
#   python -m experiments.run_scenarios idle-gpu                     run one scenario
#   python -m experiments.run_scenarios idle-gpu login-node          run several scenarios
#   python -m experiments.run_scenarios --tag single                 run every single-norm scenario
#   python -m experiments.run_scenarios --tag combo                  run every combination
#   python -m experiments.run_scenarios --tag N12                    run every scenario that uses norm N12 (also: hpc, lab, paper, review)
#   python -m experiments.run_scenarios idle-gpu --max-steps 4       override the step limit
import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if "--mode" in sys.argv:
    mode_index = sys.argv.index("--mode")
    if mode_index + 1 < len(sys.argv) and sys.argv[mode_index + 1] == "curated":
        os.environ["NORMA_CURATED_MODE"] = "1"

from norma.agent import NormaAgent
from norma.arbiter import Arbiter
from norma.llm import AnthropicLLM, LLM
from norma.org import OrgSelf
from norma.reasoner import Reasoner
from norma.tools.evaluator import NormEvaluator
from norma.tools.evaluator.instance_store import NormInstanceStore
from norma.tools.evaluator.pattern_store import NormPatternStore
from norma.tools.memory import AgentMemory
from norma.tools.server import create_server
from substrate import Principal, Substrate

from .message_logger import MessageLoggingLLM, StructuredEventLogger, new_log_path
from .model import ExperimentResult, Scenario
from .norms import NORMS
from .runner import run_experiment
from .scenarios import SANCTIONS, SCENARIOS, Spec, infer_metadata
from .curated_benchmark import load_curated_scenarios, select_curated_scenarios
from .tools import ARBITER_TOOLS, EXPERIMENT_TOOLS


# Turn one Spec into the same (Scenario, agent, server) triple that build_experiment_0 returns
def build(name: str, spec: Spec, llm: LLM | None = None, log_path=None) -> tuple[Scenario, NormaAgent, object]:
    if spec.metadata is None:
        spec.metadata = infer_metadata(name, spec)
    substrate = Substrate()
    substrate.state.principals.extend(Principal(principal) for principal in spec.principals)
    substrate.state.resources.extend(spec.resources)
    substrate.state.projects.extend(spec.projects)
    substrate.state.resource_requests.extend(spec.requests)
    substrate.state.messages.extend(spec.messages)

    # De Jure gets one pattern per distinct (norm, bindings); De Facto gets one instance per subject
    pattern_store, instance_store, pattern_ids = NormPatternStore(), NormInstanceStore(), {}
    for norm_name, subject, obj, bindings in spec.norms:
        key = (norm_name, repr(bindings))
        if key not in pattern_ids:
            pattern_ids[key] = pattern_store.insert(norm_name, *NORMS[norm_name](**bindings))
        instance_store.insert(pattern_ids[key], subject, object=obj)

    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    org = OrgSelf(spec.policy or {norm_name: SANCTIONS[norm_name] for norm_name, *_ in spec.norms})
    server = create_server(AgentMemory(), evaluator)

    if llm is None:
        llm = AnthropicLLM(
            model=os.getenv("NORMA_MODEL", "claude-haiku-4-5-20251001"),
            tool_executor=lambda tool, arguments: asyncio.run(
                server._tool_manager.call_tool(tool, arguments, convert_result=True)
            ),
        )
    readable_log_path = log_path or new_log_path(name)
    model = os.getenv("NORMA_MODEL", "claude-haiku-4-5-20251001")
    event_logger = StructuredEventLogger(
        Path(readable_log_path).with_suffix(".jsonl"),
        base={
            "experiment": name,
            "condition": getattr(spec.metadata, "goal_norm_relationship", "default"),
            "provider": "anthropic",
            "model": model,
            "scenario_id": name,
            "configuration_version": "scenario-harness-1",
        },
    )
    llm = MessageLoggingLLM(
        llm,
        readable_log_path,
        event_logger=event_logger,
        provider="anthropic",
        model=model,
    )

    agent = NormaAgent(
        reasoner=Reasoner(llm, EXPERIMENT_TOOLS),
        arbiter=Arbiter(llm, ARBITER_TOOLS),
        substrate=substrate,
    )
    scenario = Scenario(
        name=name,
        goal=spec.goal,
        sanctions=org.get_possible_sanctions(),
        goal_reached=spec.goal_reached,
        evaluator=evaluator,
        org=org,
        world_events=spec.world_events,
        metadata=spec.metadata,
    )
    return scenario, agent, server


# The given names, else every scenario; then keep only those with `tag`
def select(names: list[str] | None = None, tag: str | None = None) -> list[str]:
    unknown = set(names or []) - SCENARIOS.keys()
    if unknown:
        raise SystemExit(f"Unknown scenario(s): {', '.join(sorted(unknown))}. Use --list.")
    chosen = [name for name in (names or SCENARIOS) if tag is None or tag in SCENARIOS[name]().tags]
    if tag and not chosen:
        raise SystemExit(f"No scenario has the tag {tag!r} (tags are case-sensitive). Use --list.")
    return chosen


# Run the selected scenarios and return their results by name
def run(names: list[str], llm: LLM | None = None, max_steps: int | None = None) -> dict[str, ExperimentResult]:
    results = {}
    for name in names:
        spec = SCENARIOS[name]()
        if spec.metadata is None:
            spec.metadata = infer_metadata(name, spec)
        scenario, agent, _server = build(name, spec, llm)
        results[name] = run_experiment(scenario, agent, max_steps=max_steps or spec.max_steps)
    return results


def main() -> None:
    load_dotenv()  # read ANTHROPIC_API_KEY and NORMA_MODEL from .env
    parser = argparse.ArgumentParser(description="Run Norma scenarios.")
    parser.add_argument("names", nargs="*", help="scenario names (default: all)")
    parser.add_argument("--mode", choices=("dynamic", "curated"), default="dynamic")
    parser.add_argument("--tag", help="only scenarios with this tag")
    parser.add_argument("--seed", type=int, default=0, help="seed for curated ID sampling")
    parser.add_argument("--limit", type=int, help="number of curated IDs to sample")
    parser.add_argument("--max-steps", type=int, help="override each scenario's step limit")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args()

    if args.mode == "curated":
        curated = load_curated_scenarios()
        names = select_curated_scenarios(args.names or None, seed=args.seed, limit=args.limit)
        if args.tag:
            names = [name for name in names if args.tag in curated[name].metadata.tags]
        if args.list:
            for name in names:
                spec = curated[name]
                print(f"{name:20} {', '.join(sorted(spec.metadata.tags))}")
            return
        for name in names:
            spec = curated[name]
            scenario, agent, _server = build(name, spec, log_path=None)
            result = run_experiment(scenario, agent, max_steps=args.max_steps or spec.max_steps)
            print(f"{name}: {'achieved' if result.achieved else 'not achieved'} in {len(result.steps)} steps")
        return

    if args.list:
        for name, make in SCENARIOS.items():
            print(f"{name:20} {', '.join(sorted(make().tags))}")
        return

    for name, result in run(select(args.names, args.tag), max_steps=args.max_steps).items():
        print(f"{name}: {'achieved' if result.achieved else 'not achieved'} in {len(result.steps)} steps")
        for index, step in enumerate(result.steps, start=1):
            action = step.proposal.action
            status = "approved" if step.decision.approved else "rejected"
            print(f"  {index}. {getattr(action.type, 'value', action.type)} {action.parameters} ({status})")
        for decision in result.sanctions:
            print(f"  sanction: {decision.subject} <- {decision.sanction.value} (step {decision.timestamp})")


if __name__ == "__main__":
    main()
