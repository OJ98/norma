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

Experiment 0 starts with `gpu-1` unallocated. The goal is to request the GPU
and then use it. Success requires both a matching resource request and
`gpu-1.in_use_by == "researcher-1"`.

### Norm Violations And Org

Each experiment may configure an environment-level `OrgSelf` with a
deterministic policy mapping norm identifiers to `SanctionType` values. The
policy belongs to the experiment organization and is not exposed to the
agent. For example, Experiment 0 maps `request_before_use` to a warning.
Org exposes only the distinct sanction labels currently in play for the
Reasoner and Arbiter prompts.

After an approved action is executed, the runner asks the `NormEvaluator` to
inspect the resulting state. The evaluator returns normative statuses only;
the runner converts violated statuses into environment-level violation events
and passes them to `OrgSelf`. Org returns one or more `SanctionDecision`
objects when a policy applies, or `None` when no policy applies. Policies may
use ordered `SanctionRule` values to select different sanctions for different
violation events. The substrate records returned decisions in its sanction
state; Org does not apply sanctions directly. Decisions are also available as
`result.sanctions`.

Scenarios may schedule deterministic world events with the `world_events` field
of `Scenario`. Events are keyed by logical step and execute before the agent's
turn, so later reasoning can observe state changes such as approvals or author
agreements that occur independently of the active agent.

### Adding A Sanction Policy

For a fixed response, map a norm identifier directly to a sanction:

```python
org = OrgSelf({"request_before_use": SanctionType.WARNING})
```

Use ordered `SanctionRule` values when the response depends on the violation
event. The first matching rule is selected, and one rule can produce multiple
sanctions:

```python
org = OrgSelf({
    "ai_use_disclosure": [
        SanctionRule(
            when=lambda violation: violation.event_type == "publish",
            sanctions=(SanctionType.PAPER_WITHDRAWAL,),
        ),
        SanctionRule(
            when=lambda violation: violation.event_type == "undisclosed_ai_use",
            sanctions=(SanctionType.REPUTATION_LOSS, SanctionType.EXPULSION),
        ),
    ],
})
```

Import `OrgSelf`, `SanctionRule`, and `SanctionType` in the experiment module.
The runner passes the action type as `violation.event_type` and the logical
step as `violation.timestamp`.

### Adding World Events

Define a function that receives the shared `Substrate`, then register it under
the logical step when it should run:

```python
def approve_project(substrate: Substrate) -> None:
    project = next(project for project in substrate.state.projects if project.id == "project-1")
    project.public = True


scenario = Scenario(
    name="Experiment 1",
    goal="Complete the project",
    sanctions=[],
    goal_reached=lambda state: state.projects[0].public,
    world_events={3: [approve_project]},
)
```

The runner executes all events scheduled for a step before checking the goal
or asking the agent to act. Keep events deterministic and mutate only the
shared substrate state; use them for independent actors or institutions that
are outside the active Norma agent.

## Adding A Scenario

Create a module such as `experiment_1.py` with a factory that follows the
shape of `build_experiment_0`:

1. Create one `Substrate` and initialize its principals, resources, and state.
2. Create `NormPatternStore` and `NormInstanceStore` entries.
3. Create `NormEvaluator` with that same substrate.
4. Create an `OrgSelf` with the experiment's norm-to-sanction policy.
5. Create the MCP server with `create_server(memory, evaluator)`.
6. Create the `Reasoner`, `Arbiter`, and `NormaAgent` using that same substrate.
7. Return a `Scenario`, agent, and server.

The `Scenario` needs:

```python
Scenario(
    name="Experiment 1",
    goal="A natural-language goal for the agent",
    sanctions=["warning"],  # fallback when no Org is configured
    goal_reached=lambda state: ...,  # inspect SubstrateState
    evaluator=evaluator,
    org=org,
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
# SanctionDecision instances produced by OrgSelf.
print(result.sanctions)
```

For deterministic tests, pass a scripted or mock `LLM` to the factory. For a
live run, omit it and configure the Anthropic API and optional `NORMA_MODEL`
environment variable.