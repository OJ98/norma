from experiments.experiment_0 import build_experiment_0
from experiments.runner import run_experiment


def main() -> None:
    scenario, agent, _server = build_experiment_0()
    result = run_experiment(scenario, agent)

    print(f"{scenario.name}: {'achieved' if result.achieved else 'not achieved'}")
    print(f"steps: {len(result.steps)}")
    print(f"message log: {agent.reasoner.llm.log_path}")
    for index, step in enumerate(result.steps, start=1):
        action = step.proposal.action
        status = "approved" if step.decision.approved else "rejected"
        print(f"{index}. {action.type} {action.parameters} ({status})")


if __name__ == "__main__":
    main()
