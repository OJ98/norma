# Commands (run from the repository root):
#   python -m experiments.run_scenarios --list                  list the 55 curated scenarios with their tags
#   python -m experiments.run_scenarios                         run every curated scenario
#   python -m experiments.run_scenarios cb-001                  run one scenario
#   python -m experiments.run_scenarios cb-001 cb-022           run several scenarios
#   python -m experiments.run_scenarios --seed 7 --limit 5      run a reproducible random sample
#   python -m experiments.run_scenarios --tag N12               run every scenario with a tag (also: single, combo, hpc, conflict, ...)
#   python -m experiments.run_scenarios cb-001 --max-steps 4    override the step limit
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from norma.agent import NormaAgent
from norma.arbiter import Arbiter
from norma.llm import LLM, configured_provider, create_configured_llm
from norma.org import OrgSelf
from norma.reasoner import Reasoner
from norma.tools.evaluator import NormEvaluator
from norma.tools.evaluator.instance_store import NormInstanceStore
from norma.tools.evaluator.pattern_store import NormPatternStore
from norma.tools.memory import AgentMemory
from norma.tools.server import create_server
from substrate import Principal, SanctionType, Substrate

from .message_logger import MessageLoggingLLM, StructuredEventLogger, new_log_path
from .model import ExperimentResult, Scenario
from .norms import NORMS
from .runner import run_experiment
from .scenarios import SANCTIONS, Spec, load_curated_scenarios, select_curated_scenarios
from .tools import ARBITER_TOOLS, EXPERIMENT_TOOLS


# Turn one Spec into a (Scenario, agent, server) triple
def build(name: str, spec: Spec, llm: LLM | None = None, log_path=None) -> tuple[Scenario, NormaAgent, object]:
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
    provider, model = configured_provider()

    if llm is None:
        llm = create_configured_llm(
            tool_executor=lambda tool, arguments: asyncio.run(
                server._tool_manager.call_tool(tool, arguments, convert_result=True)
            ),
        )
    readable_log_path = log_path or new_log_path(name)
    event_logger = StructuredEventLogger(
        Path(readable_log_path).with_suffix(".jsonl"),
        base={
            "experiment": name,
            "condition": getattr(spec.metadata, "goal_norm_relationship", "default"),
            "provider": provider,
            "model": model,
            "scenario_id": name,
            "configuration_version": "scenario-harness-1",
        },
    )
    llm = MessageLoggingLLM(
        llm,
        readable_log_path,
        event_logger=event_logger,
        provider=provider,
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
        # The agent sees every sanction the org can impose, not only those tied to this scenario's norms
        sanctions=[sanction.value for sanction in SanctionType],
        goal_reached=spec.goal_reached,
        evaluator=evaluator,
        org=org,
        world_events=spec.world_events,
        metadata=spec.metadata,
    )
    return scenario, agent, server


# The given curated IDs (else all, or a seeded sample of `limit`); then keep only those with `tag`
def select(specs: dict[str, Spec], names: list[str] | None = None, tag: str | None = None, seed: int = 0,
           limit: int | None = None) -> list[str]:
    try:
        chosen = select_curated_scenarios(names or None, seed=seed, limit=limit)
    except ValueError as error:
        raise SystemExit(f"{error}. Use --list.")
    if tag:
        chosen = [name for name in chosen if tag in specs[name].metadata.tags]
        if not chosen:
            raise SystemExit(f"No scenario has the tag {tag!r} (tags are case-sensitive). Use --list.")
    return chosen


# Run the selected scenarios and return their results by ID. Load the specs
# once per run: seed message IDs come from a global counter, so reloading
# would change the IDs the agent sees.
def run(names: list[str], specs: dict[str, Spec] | None = None, llm: LLM | None = None,
        max_steps: int | None = None) -> dict[str, ExperimentResult]:
    specs = specs or load_curated_scenarios()
    results = {}
    for name in names:
        spec = specs[name]
        scenario, agent, _server = build(name, spec, llm)
        results[name] = run_experiment(scenario, agent, max_steps=max_steps or spec.max_steps)
    return results


def main() -> None:
    load_dotenv()  # read provider API keys and NORMA_MODEL from .env
    parser = argparse.ArgumentParser(description="Run the curated Norma benchmark.")
    parser.add_argument("names", nargs="*", help="curated scenario IDs such as cb-001 (default: all)")
    parser.add_argument("--tag", help="only scenarios with this tag")
    parser.add_argument("--seed", type=int, default=0, help="seed for --limit sampling")
    parser.add_argument("--limit", type=int, help="number of scenario IDs to sample")
    parser.add_argument("--max-steps", type=int, help="override each scenario's step limit")
    parser.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = parser.parse_args()

    specs = load_curated_scenarios()
    names = select(specs, args.names, args.tag, seed=args.seed, limit=args.limit)
    if args.list:
        for name in names:
            print(f"{name:10} {', '.join(specs[name].metadata.tags)}")
        return

    for name, result in run(names, specs, max_steps=args.max_steps).items():
        print(f"{name}: {'achieved' if result.achieved else 'not achieved'} in {len(result.steps)} steps")
        for index, step in enumerate(result.steps, start=1):
            action = step.proposal.action
            status = "approved" if step.decision.approved else "rejected"
            print(f"  {index}. {getattr(action.type, 'value', action.type)} {action.parameters} ({status})")
        for decision in result.sanctions:
            print(f"  sanction: {decision.subject} <- {decision.sanction.value} (step {decision.timestamp})")


if __name__ == "__main__":
    main()
