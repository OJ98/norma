from substrate import ActionType, Principal, Substrate

from norma.agent import NormaAgent
from norma.llm import LLM, LLMResponse
from norma.reasoner import Reasoner
from norma.arbiter import Arbiter


class MockLLM(LLM):
    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict],
        output_schema: dict | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tools": tools,
                "output_schema": output_schema,
            }
        )
        if not self.responses:
            raise AssertionError("No mock LLM response left to return.")
        return self.responses.pop(0)


def test_norma_agent_step_approves_and_executes_action():
    llm = MockLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[],
                structured_output={
                    "action": {
                        "type": "send",
                        "actor": "researcher_1",
                        "parameters": {
                            "message_id": "msg-1",
                            "content": "Please share the dataset.",
                            "recipient_id": "researcher_2",
                        },
                    },
                    "rationale": "Request the missing dataset to complete the experiment.",
                },
            ),
            LLMResponse(
                content=None,
                tool_calls=[],
                structured_output={
                    "approved": True,
                    "rationale": "The request advances the goal and does not violate the documented norms.",
                },
            ),
        ]
    )

    substrate = Substrate()
    substrate.state.principals = [
        Principal(id="researcher_1"),
        Principal(id="researcher_2"),
    ]

    agent = NormaAgent(
        reasoner=Reasoner(llm, []),
        arbiter=Arbiter(llm, []),
        substrate=substrate,
    )

    result = agent.step(
        goal="Complete the experiment",
        sanctions=["warning"],
    )

    assert result.proposal.action.type == ActionType.SEND
    assert result.proposal.action.parameters["recipient_id"] == "researcher_2"
    assert result.decision.approved is True
    assert result.execution_result is not None
    assert result.execution_result.success is True
    assert result.execution_result.message.startswith("Message msg-1 sent")
    assert len(llm.calls) == 2
