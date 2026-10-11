import pytest
import json

pytest.importorskip("mcp.server.fastmcp")

from norma.llm import LLM, LLMResponse
from norma.tools.server import FastMCP
from substrate import Action, ActionType

from experiments.experiment_0 import PRINCIPAL_ID, RESOURCE_ID, build_experiment_0
from experiments.runner import run_experiment


class ScriptedLLM(LLM):
    def __init__(self):
        self.responses = [
            {"action": {"type": "request", "actor": PRINCIPAL_ID, "parameters": {"resource_id": RESOURCE_ID}}, "rationale": "Request first."},
            {"approved": True, "rationale": "The request is appropriate."},
            {"action": {"type": "use", "actor": PRINCIPAL_ID, "parameters": {"resource_id": RESOURCE_ID}}, "rationale": "Use the requested GPU."},
            {"approved": True, "rationale": "The use is approved."},
        ]

    def generate(self, system_prompt, user_prompt, tools, output_schema=None):
        return LLMResponse(content=None, tool_calls=[], structured_output=self.responses.pop(0))


def test_experiment_0_constructs_shared_substrate_and_goal():
    scenario, agent, server = build_experiment_0(ScriptedLLM())

    assert isinstance(server, FastMCP)
    assert agent.substrate.state.resources[0].allocated_to == None
    assert scenario.goal_reached(agent.substrate.get_state()) is False
    assert [tool["name"] for tool in agent.reasoner.tools] == [
        "store_memory",
        "retrieve_memory",
        "evaluate_action",
    ]
    assert "store_memory" in [tool["name"] for tool in agent.reasoner.tools]
    assert "store_memory" not in [tool["name"] for tool in agent.arbiter.tools]


def test_experiment_0_goal_requires_request_before_use():
    scenario, agent, _server = build_experiment_0(ScriptedLLM())
    agent.substrate.state.resources[0].in_use_by = PRINCIPAL_ID

    assert scenario.goal_reached(agent.substrate.get_state()) is False

    agent.substrate.execute(
        Action(
            ActionType.REQUEST,
            PRINCIPAL_ID,
            {"resource_id": RESOURCE_ID},
        )
    )
    assert scenario.goal_reached(agent.substrate.get_state()) is True


def test_runner_reaches_experiment_0_goal():
    scenario, agent, _server = build_experiment_0(ScriptedLLM())

    result = run_experiment(scenario, agent, max_steps=3)

    assert result.achieved is True
    assert len(result.steps) == 2
    assert scenario.goal_reached(agent.substrate.get_state()) is True


def test_completed_experiment_writes_reconstructable_jsonl_log(tmp_path):
    log_path = tmp_path / "experiment.log"
    scenario, agent, _server = build_experiment_0(ScriptedLLM(), log_path=log_path)

    result = run_experiment(scenario, agent, max_steps=3)

    events = [
        json.loads(line)
        for line in log_path.with_suffix(".jsonl").read_text(encoding="utf-8").splitlines()
    ]
    by_type = {}
    for event in events:
        by_type.setdefault(event["event_type"], []).append(event)

    assert result.achieved is True
    assert {"RUN_STARTED", "SCENARIO_STARTED", "REASONER_PROPOSED", "NORM_EVALUATED",
            "ARBITER_DECIDED", "ACTION_EXECUTED", "STATE_CHANGED",
            "SCENARIO_COMPLETED", "RUN_COMPLETED"} <= by_type.keys()
    assert by_type["SCENARIO_STARTED"][0]["goal"] == scenario.goal
    assert by_type["SCENARIO_STARTED"][0]["step_limit"] == 3
    assert len(by_type["REASONER_PROPOSED"]) == 2
    assert [event["approved"] for event in by_type["ARBITER_DECIDED"]] == [True, True]
    assert all(event["executed"] for event in by_type["ARBITER_DECIDED"])
    assert all(event["result"]["success"] for event in by_type["ACTION_EXECUTED"])
    assert all(
        "state_before" in event and "state_after" in event
        for event in by_type["STATE_CHANGED"]
        if event["change_type"] == "agent_action"
    )
    executed_norms = [
        event for event in by_type["NORM_EVALUATED"] if event["phase"] == "executed"
    ]
    assert executed_norms
    assert all(
        evaluation["status"] in {"active", "discharged", "violated", "inactive"}
        for event in executed_norms
        for evaluation in event["evaluations"]
    )
    completed = by_type["SCENARIO_COMPLETED"][0]
    assert completed["goal_status"]["achieved"] is True
    assert completed["goal_status"]["actions"] == 2
    assert all(event["run_id"] == events[0]["run_id"] for event in events)
    assert any(event["component"] == "reasoner" for event in by_type["MODEL_CALL_COMPLETED"])
    assert any(event["component"] == "arbiter" for event in by_type["MODEL_CALL_COMPLETED"])