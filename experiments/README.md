# Experiment Harness

This folder runs the frozen, versioned curated benchmark of 55 scenarios
(`cb-001` to `cb-055`). For each scenario, `run_scenarios.py` builds a shared
`Substrate`, the normative evaluator, the organization (`OrgSelf`), an agent,
and the MCP tools used during deliberation. The generic runner (`runner.py`)
then executes agent steps until the scenario reports success or a step limit
is reached.

| File | Contents |
| --- | --- |
| `scenarios.py` | Every scenario: `Spec`, the `SANCTIONS` policy, shared building blocks, world events and goal checks, one builder per scenario, and the `CURATED_RECORDS` table with its loader |
| `norms.py` | Norm definitions referenced by name from each `Spec` |
| `run_scenarios.py` | Command line entry point and `build()` |
| `runner.py` | The step loop, norm evaluation, and sanctions |
| `model.py` | `Scenario`, `ScenarioMetadata`, and `ExperimentResult` |
| `message_logger.py` | Readable transcripts and structured JSONL event logs |
| `tools.py` | MCP tools offered to the Reasoner and Arbiter |

## Running the benchmark

Run from the repository root:

```powershell
python -m experiments.run_scenarios --list
python -m experiments.run_scenarios
python -m experiments.run_scenarios cb-001 cb-022
python -m experiments.run_scenarios --seed 7 --limit 5
python -m experiments.run_scenarios --tag N12
python -m experiments.run_scenarios cb-001 --max-steps 4
```

Each run writes a readable log file under `experiments/logs/` and a
machine-readable JSONL event log beside it (`.jsonl`).

### Structured event logs

The JSONL log is the source of truth for post-run analysis; the readable
transcript is retained for debugging. Each line is an event with a stable
`event_type`, `run_id`, sequence number, and UTC timestamp. Run and scenario
metadata are attached to lifecycle events. The runner records
`REASONER_PROPOSED`, `NORM_EVALUATED`, `ARBITER_DECIDED`, `ACTION_EXECUTED`,
`STATE_CHANGED`, sanction, goal, and completion events without calculating
paper metrics during execution.

Model and tool telemetry is recorded as `MODEL_CALL_*` and
`TOOL_CALL_COMPLETED` events, including component (Reasoner or Arbiter),
available token usage, and latency. Proposal-time norm tool results and
post-execution norm evaluations have distinct `phase` values. State snapshots
are stored only on `STATE_CHANGED` events; other events refer to them by
`state_id`, `state_before_id`, or `state_after_id`. This preserves the
distinction between proposed, evaluated, approved, and executed actions and
provides the observations needed to reconstruct success, violations,
dispositions, progress, efficiency, and overhead metrics after a run.

### Norm Violations And Org

Each scenario configures an environment-level `OrgSelf` with a deterministic
policy mapping norm identifiers to `SanctionType` values; by default this is
the `SANCTIONS` table in `scenarios.py`, restricted to the scenario's norms.
The policy belongs to the organization and is not exposed to the agent. The
Reasoner and Arbiter prompts list every `SanctionType` the organization can
impose (`Scenario.sanctions`), not only those tied to the scenario's norms.

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

To give one scenario its own policy, set the `policy` field of its `Spec`.
The runner passes the action type as `violation.event_type` and the logical
step as `violation.timestamp`.

### Adding World Events

Define a function that receives the shared `Substrate`, then register it under
the logical step when it should run:

```python
def approve_project(substrate: Substrate) -> None:
    project = next(project for project in substrate.state.projects if project.id == "project-1")
    project.public = True


Spec(
    ...,
    world_events={3: [approve_project]},
)
```

`scenarios.py` already provides common events (`message`, `reply`, `serve`,
`free`, `repair`, `decide`, `when`) and `timeline()` to schedule them at one
step (`at=`) or at a step and every later step (`after=`).

The runner executes all events scheduled for a step before checking the goal
or asking the agent to act. Keep events deterministic and mutate only the
shared substrate state; use them for independent actors or institutions that
are outside the active Norma agent.

## The curated benchmark

The versioned `CURATED_RECORDS` table in [`scenarios.py`](./scenarios.py)
contains exactly 55 fixed records (`cb-001` through `cb-055`). Each record
names its builder function and declares its domain and norm IDs; its sanction
values come from `SANCTIONS`, and its goal-norm relationship (`aligned`,
`delayed`, or `conflict`) from the builder's tags. `load_curated_scenarios()`
validates the table, builds every scenario once, and attaches
`ScenarioMetadata`. Load the scenarios only once per run: seed message IDs
come from a global counter, so building again changes the IDs the agent sees.

## Adding A Scenario

1. Write a builder in `scenarios.py` that returns a `Spec`: the goal, a
   `goal_reached` check on the state, principals, resources, projects,
   messages, `norm(...)` entries, world events, tags, and `max_steps`. Tags
   must include exactly one of `aligned`, `delayed`, or `conflict`.
2. Add a `_record("cb-056", ...)` entry to `CURATED_RECORDS` that names the
   builder, then update the expected count in `validate_curated_records()`.
3. Add any new norm to `norms.py` and to `SANCTIONS`.

Keep the success predicate specific to the scenario. It should inspect the
final state, including any required prerequisite actions, rather than relying
only on the last proposed action.

Run a scenario with the shared runner:

```python
from experiments.run_scenarios import build
from experiments.runner import run_experiment
from experiments.scenarios import load_curated_scenarios

spec = load_curated_scenarios()["cb-001"]
scenario, agent, _server = build("cb-001", spec)
result = run_experiment(scenario, agent, max_steps=spec.max_steps)
print(result.achieved, len(result.steps))
# SanctionDecision instances produced by OrgSelf.
print(result.sanctions)
```

For deterministic tests, pass a scripted or mock `LLM` to `build()`. For a
live run, omit it and configure the provider API key and optional
`NORMA_MODEL` environment variable.
