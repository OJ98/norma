# Norma

Norma runs agent scenarios with normative evaluation. The scenarios listed in
[`scenario_tiers.xlsx`](./scenario_tiers.xlsx) are implemented in
[`experiments/scenarios.py`](./experiments/scenarios.py) and can be selected by
their value in the workbook's **Scenario** column.

## Setup

From the repository root, create an environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Configure the Anthropic key for live runs:

```powershell
Copy-Item .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

`NORMA_MODEL` is optional. If it is not set, Norma uses
`claude-haiku-4-5-20251001`.

## Find and run scenarios

List every scenario currently registered with the runner:

```powershell
python -m experiments.run_scenarios --list
```

Run one workbook scenario by its exact name:

```powershell
python -m experiments.run_scenarios idle-gpu
```

Run several scenarios in one command:

```powershell
python -m experiments.run_scenarios idle-gpu login-node
```

Run scenarios by tag. Tags are shown by `--list` and are case-sensitive:

```powershell
python -m experiments.run_scenarios --tag single
python -m experiments.run_scenarios --tag combo
python -m experiments.run_scenarios --tag hpc
python -m experiments.run_scenarios --tag N12
```

Run the frozen 50-scenario curated benchmark without dynamic expansion:

```powershell
python -m experiments.run_scenarios --mode curated
python -m experiments.run_scenarios --mode curated --seed 7 --limit 5
python -m experiments.validate_benchmark --curated
```

The default `--mode dynamic` behavior remains available for future scenario
expansion work.

Limit the number of agent steps while debugging:

```powershell
python -m experiments.run_scenarios gpu-request --max-steps 4
```

The command prints whether each goal was achieved, each proposed action and
approval status, and any sanctions. Live runs write readable LLM transcripts
to [`experiments/logs/`](./experiments/logs/).

The current workbook contains 38 benchmark rows. The frozen curated benchmark
is a separate, versioned set of exactly 50 scenarios and is validated with
`python -m experiments.validate_benchmark --curated`.

## Small built-in experiment

To run the original GPU request-before-use experiment:

```powershell
python -m experiments.run_experiment_0
```

## Tests without an API key

The experiment tests use scripted LLM responses, so they do not require
`ANTHROPIC_API_KEY`:

```powershell
python -m pytest tests/test_experiment_0.py
```
