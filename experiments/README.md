# Experiment Harness

This folder contains small, reproducible experiments for Norma. Each experiment
builds a scenario, a shared `Substrate`, the normative evaluator, an agent, and
the MCP tools used during deliberation. The generic runner then executes agent
steps until the scenario reports success or a step limit is reached.

## Experiment 0

Run it from the repository root:

```powershell
python -m experiments.run_experiment_0
```

The command prints the result, trajectory, and the path to a new readable log
file under `experiments/logs/`.

Experiment 0 starts with `gpu-1` allocated to `researcher-1`. The goal is to
request the GPU and then use it. Success requires both a matching resource
request and `gpu-1.in_use_by == "researcher-1"`.

## Adding A Scenario

Create a module such as `experiment_1.py` with a factory that follows the
shape of `build_experiment_0`:

1. Create one `Substrate` and initialize its principals, resources, and state.
2. Create `NormPatternStore` and `NormInstanceStore` entries.
3. Create `NormEvaluator` with that same substrate.
4. Create the MCP server with `create_server(memory, evaluator)`.
5. Create the `Reasoner`, `Arbiter`, and `NormaAgent` using that same substrate.
6. Return a `Scenario`, agent, and server.

The `Scenario` needs:

```python
Scenario(
    name="Experiment 1",
    goal="A natural-language goal for the agent",
    sanctions=["warning"],
    goal_reached=lambda state: ...,  # inspect SubstrateState
)
```

Keep the success predicate specific to the scenario. It should inspect the
final state, including any required prerequisite actions, rather than relying
only on the last proposed action.

Run a scenario with the shared runner:

```python
from experiments.runner import run_experiment

result = run_experiment(scenario, agent, max_steps=10)
print(result.achieved, len(result.steps))
```

For deterministic tests, pass a scripted or mock `LLM` to the factory. For a
live run, omit it and configure the Anthropic API and optional `NORMA_MODEL`
environment variable.