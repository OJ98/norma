import pytest

from action import Action
from norma.arbiter import Arbiter
from norma.arbiter.model import ARBITER_OUTPUT_SCHEMA, ArbiterDecision
from norma.llm import LLM, LLMResponse
from norma.reasoner.model import ReasonerProposal


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


def test_review_returns_approved_decision():
    response = LLMResponse(
        content='{"approved": true, "rationale": "The action is appropriate."}',
        tool_calls=[],
        structured_output={
            "approved": True,
            "rationale": "The action is appropriate.",
        },
    )

    llm = MockLLM(response)
    tools = [{"name": "evaluate_norm"}]
    arbiter = Arbiter(llm, tools)

    proposal = ReasonerProposal(
        action=Action(
            type="send_message",
            actor="researcher_1",
            parameters={
                "recipient": "researcher_2",
            },
        ),
        rationale="Contact the other researcher.",
    )

    decision = arbiter.review(
        goal="Coordinate the experiment",
        state="Researcher 2 has the required data.",
        sanctions="Warning, resource restriction",
        proposal=proposal,
    )

    assert isinstance(decision, ArbiterDecision)
    assert decision.approved is True
    assert decision.rationale == "The action is appropriate."


def test_review_returns_rejected_decision():
    response = LLMResponse(
        content='{"approved": false, "rationale": "The action violates an applicable norm."}',
        tool_calls=[],
        structured_output={
            "approved": False,
            "rationale": "The action violates an applicable norm.",
        },
    )

    llm = MockLLM(response)
    arbiter = Arbiter(llm, [])

    proposal = ReasonerProposal(
        action=Action(
            type="allocate",
            actor="researcher_1",
            parameters={"resource_id": "gpu-1"},
        ),
        rationale="Allocate the GPU to finish the experiment.",
    )

    decision = arbiter.review(
        goal="Finish the experiment",
        state="GPU-1 is currently allocated to another researcher.",
        sanctions="Resource restriction",
        proposal=proposal,
    )

    assert decision.approved is False
    assert decision.rationale == "The action violates an applicable norm."


def test_review_passes_context_and_proposal_to_llm():
    response = LLMResponse(
        content=None,
        tool_calls=[],
        structured_output={
            "approved": True,
            "rationale": "Approved.",
        },
    )

    llm = MockLLM(response)
    arbiter = Arbiter(llm, [])

    proposal = ReasonerProposal(
        action=Action(
            type="send_message",
            actor="researcher_1",
            parameters={"recipient": "researcher_2"},
        ),
        rationale="Ask for the required data.",
    )

    arbiter.review(
        goal="Complete the experiment",
        state="The required data is missing.",
        sanctions="Warning",
        proposal=proposal,
    )

    assert "Complete the experiment" in llm.user_prompt
    assert "The required data is missing." in llm.user_prompt
    assert "Warning" in llm.user_prompt
    assert "send_message" in llm.user_prompt
    assert "researcher_1" in llm.user_prompt
    assert "Ask for the required data." in llm.user_prompt


def test_review_passes_tools_and_schema():
    response = LLMResponse(
        content=None,
        tool_calls=[],
        structured_output={
            "approved": True,
            "rationale": "Approved.",
        },
    )

    llm = MockLLM(response)
    tools = [{"name": "evaluate_norm"}]
    arbiter = Arbiter(llm, tools)

    proposal = ReasonerProposal(
        action=Action(
            type="wait",
            actor="researcher_1",
            parameters={},
        ),
        rationale="Wait.",
    )

    arbiter.review(
        goal="Complete the experiment",
        state="Waiting",
        sanctions="Warning",
        proposal=proposal,
    )

    assert llm.tools == tools
    assert llm.output_schema == ARBITER_OUTPUT_SCHEMA


def test_review_without_structured_output_raises():
    response = LLMResponse(
        content="some response",
        tool_calls=[],
        structured_output=None,
    )

    llm = MockLLM(response)
    arbiter = Arbiter(llm, [])

    proposal = ReasonerProposal(
        action=Action(
            type="wait",
            actor="researcher_1",
            parameters={},
        ),
        rationale="Wait.",
    )

    with pytest.raises(RuntimeError, match="structured output"):
        arbiter.review(
            goal="Complete the experiment",
            state="Waiting",
            sanctions="Warning",
            proposal=proposal,
        )