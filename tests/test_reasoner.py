import pytest

from substrate import Action, ActionType
from norma.llm import LLM, LLMResponse
from norma.reasoner import Reasoner
from norma.reasoner.model import REASONER_OUTPUT_SCHEMA, ReasonerProposal


class MockLLM(LLM):

    def __init__(self, response: LLMResponse):
        self.response = response
        self.system = None
        self.user_prompt = None
        self.tools = None
        self.output_schema = None

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        output_schema: dict | None = None,
    ) -> LLMResponse:
        self.system = system_prompt
        self.user_prompt = user_prompt
        self.tools = tools
        self.output_schema = output_schema
        return self.response


def test_propose_returns_reasoner_proposal():
    response = LLMResponse(
        content='{"action": {"type": "send_message", "principal_id": "researcher_1", "parameters": {"recipient": "researcher_2"}}, "rationale": "Contact the other researcher."}',
        tool_calls=[],
        structured_output={
            "action": {
                "type": "send_message",
                "principal_id": "researcher_1",
                "parameters": {
                    "recipient": "researcher_2",
                },
            },
            "rationale": "Contact the other researcher.",
        },
    )

    llm = MockLLM(response)
    tools = [{"name": "retrieve_memory"}]
    reasoner = Reasoner(llm, tools)

    proposal = reasoner.propose(
        goal="Coordinate the experiment",
        state="Researcher 2 has the required data.",
        sanctions="Warning, resource restriction",
    )

    assert isinstance(proposal, ReasonerProposal)
    assert proposal.action == Action(
        type=ActionType.SEND,
        principal_id="researcher_1",
        parameters={
            "recipient": "researcher_2",
        },
    )
    assert proposal.rationale == "Contact the other researcher."


def test_propose_passes_context_to_llm():
    response = LLMResponse(
        content=None,
        tool_calls=[],
        structured_output={
            "action": {
                "type": "wait",
                "principal_id": "researcher_1",
                "parameters": {},
            },
            "rationale": "Wait for more information.",
        },
    )

    llm = MockLLM(response)
    tools = [{"name": "retrieve_memory"}]
    reasoner = Reasoner(llm, tools)

    reasoner.propose(
        goal="Complete the experiment",
        state="The experiment is currently running.",
        sanctions="Warning",
        arbiter_feedback="The previous action was rejected.",
    )

    assert "Complete the experiment" in llm.user_prompt
    assert "The experiment is currently running." in llm.user_prompt
    assert "Warning" in llm.user_prompt
    assert "The previous action was rejected." in llm.user_prompt


def test_propose_normalizes_use_resource_to_use():
    response = LLMResponse(
        content=None,
        tool_calls=[],
        structured_output={
            "action": {
                "type": "use_resource",
                "actor": "researcher_1",
                "parameters": {"resource_id": "gpu-1"},
            },
            "rationale": "Use the resource.",
        },
    )

    proposal = Reasoner(MockLLM(response), []).propose(
        goal="Use the GPU",
        state="The GPU is available.",
        sanctions=[],
    )

    assert proposal.action.type == ActionType.USE


def test_propose_passes_tools_and_schema():
    response = LLMResponse(
        content=None,
        tool_calls=[],
        structured_output={
            "action": {
                "type": "wait",
                "principal_id": "researcher_1",
                "parameters": {},
            },
            "rationale": "Wait.",
        },
    )

    llm = MockLLM(response)
    tools = [{"name": "retrieve_memory"}]
    reasoner = Reasoner(llm, tools)

    reasoner.propose(
        goal="Complete the experiment",
        state="Waiting",
        sanctions="Warning",
    )

    assert llm.tools == tools
    assert llm.output_schema == REASONER_OUTPUT_SCHEMA


def test_propose_without_structured_output_raises():
    response = LLMResponse(
        content="some response",
        tool_calls=[],
        structured_output=None,
    )

    llm = MockLLM(response)
    reasoner = Reasoner(llm, [])

    with pytest.raises(RuntimeError, match="structured output"):
        reasoner.propose(
            goal="Complete the experiment",
            state="Waiting",
            sanctions="Warning",
        )