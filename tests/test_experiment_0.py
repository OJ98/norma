import pytest

pytest.importorskip("mcp.server.fastmcp")

from norma.llm import LLM, LLMResponse
from norma.tools.server import FastMCP

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
    assert agent.arbiter.tools == agent.reasoner.tools


def test_experiment_0_goal_requires_request_before_use():
    scenario, agent, _server = build_experiment_0(ScriptedLLM())
    agent.substrate.state.resources[0].in_use_by = None

    assert scenario.goal_reached(agent.substrate.get_state()) is False


def test_runner_reaches_experiment_0_goal():
    scenario, agent, _server = build_experiment_0(ScriptedLLM())

    result = run_experiment(scenario, agent, max_steps=3)

    assert result.achieved is True
    assert len(result.steps) == 2
    assert scenario.goal_reached(agent.substrate.get_state()) is True