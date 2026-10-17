# Norma

Norma runs agent scenarios with normative evaluation. The frozen, versioned
benchmark of 55 curated scenarios (cb-001 to cb-055) lives in one file,
[`experiments/scenarios.py`](./experiments/scenarios.py), and is summarized in
[`scenario_tiers.xlsx`](./scenario_tiers.xlsx).

## Setup

From the repository root, create an environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Select a provider with `NORMA_PROVIDER` (`anthropic`, `openai`, or `deepseek`) and
set its key for live runs:

```powershell
Copy-Item .env.example .env
# Edit .env and set the key matching NORMA_PROVIDER
```

`NORMA_PROVIDER` defaults to `anthropic`. `NORMA_MODEL` is optional and defaults
to `claude-haiku-4-5-20251001` (Anthropic), `gpt-4o-mini` (OpenAI), or
`deepseek-chat` (DeepSeek). DeepSeek uses `DEEPSEEK_BASE_URL`, defaulting to
`https://api.deepseek.com`. DeepSeek currently receives JSON mode rather than
JSON Schema constrained decoding; Norma validates its response against the
existing output schema before returning it to the Reasoner or Arbiter.
`NORMA_MAX_TOKENS` sets the maximum generated tokens per model response and
defaults to `4096`; raise it if a provider truncates a structured response.
Deepseek integration is still being tested. 
Anthropic is the most stable.

## Find and run scenarios

List the 55 curated scenarios with their tags:

```powershell
python -m experiments.run_scenarios --list
```

Run every curated scenario:

```powershell
python -m experiments.run_scenarios
```

Note: For live demos, cb-001 has proved to be the most stable.

Run one or several scenarios by ID:

```powershell
python -m experiments.run_scenarios cb-001
python -m experiments.run_scenarios cb-001 cb-022
```

Run a reproducible random sample:

```powershell
python -m experiments.run_scenarios --seed 7 --limit 5
```

Run scenarios by tag. Tags are shown by `--list` and are case-sensitive:

```powershell
python -m experiments.run_scenarios --tag single
python -m experiments.run_scenarios --tag combo
python -m experiments.run_scenarios --tag conflict
python -m experiments.run_scenarios --tag N12
```

Limit the number of agent steps while debugging:

```powershell
python -m experiments.run_scenarios cb-001 --max-steps 4
```

The command prints whether each goal was achieved, each proposed action and
approval status, and any sanctions. The reasoner and arbiter are shown every
sanction the organization can impose, not only those tied to the scenario's
norms. Live runs write readable LLM transcripts to
[`experiments/logs/`](./experiments/logs/).

## Tests without an API key

The experiment tests use scripted LLM responses, so they do not require
`ANTHROPIC_API_KEY`:

```powershell
python -m pytest
```
