from norma.agent import NormaAgent
from norma.arbiter import Arbiter
from norma.llm import LLM, LLMResponse
from norma.org import OrgSelf
from norma.reasoner import Reasoner
from norma.tools.evaluator import NormEvaluator
from norma.tools.evaluator.instance_store import NormInstanceStore
from norma.tools.evaluator.pattern_store import NormPatternStore
from experiments.model import Scenario
from experiments.runner import run_experiment
from substrate import ActionType, Principal, Resource, ResourceType, SanctionType, Substrate, ViolationEvent


def test_org_returns_policy_decision_with_violation_data_and_timestamp():
    org = OrgSelf({"request_before_use": SanctionType.WARNING}, clock=lambda: 123)
    violation = ViolationEvent(7, "researcher-1", "gpu-1", "request_before_use")

    decision = org.respond(violation)

    assert decision is not None
    assert decision.violation_id == 7
    assert decision.subject == "researcher-1"
    assert decision.object == "gpu-1"
    assert decision.sanction == SanctionType.WARNING
    assert decision.timestamp == 123
    assert decision.reason == "Policy for norm request_before_use imposes a warning."


def test_org_ignores_unmapped_norm_and_none_object():
    org = OrgSelf({"request_before_use": SanctionType.WARNING}, clock=lambda: 123)

    assert org.respond(ViolationEvent(1, "p1", None, "other_norm")) is None

    decision = org.respond(ViolationEvent(2, "p1", None, "request_before_use"))
    assert decision is not None
    assert decision.object is None


def test_org_does_not_duplicate_a_violation():
    org = OrgSelf({"norm": SanctionType.WARNING}, clock=lambda: 123)
    violation = ViolationEvent(4, "p1", "resource-1", "norm")

    assert org.respond(violation) is not None
    assert org.respond(violation) is None


def test_runner_passes_violations_to_org_and_applies_sanction():
    substrate = Substrate()
    substrate.state.principals.append(Principal("p1"))
    substrate.state.resources.append(Resource("resource-1", ResourceType.COMPUTE))

    pattern_store = NormPatternStore()
    instance_store = NormInstanceStore()
    pattern_id = pattern_store.insert(
        "must_not_use",
        lambda action, state: action.type in (ActionType.USE, "use"),
        lambda action, state: False,
        lambda action, state: True,
    )
    instance_store.insert(pattern_id, "p1", object="resource-1")
    evaluator = NormEvaluator(pattern_store, instance_store, substrate)
    org = OrgSelf({"must_not_use": SanctionType.WARNING}, clock=lambda: 456)

    llm = ScriptedLLM()
    agent = NormaAgent(Reasoner(llm, []), Arbiter(llm, []), substrate)
    scenario = Scenario(
        name="Org test",
        goal="Use the resource",
        sanctions=["legacy-value-that-must-not-be-used"],
        goal_reached=lambda state: state.resources[0].in_use_by == "p1",
        evaluator=evaluator,
        org=org,
    )

    result = run_experiment(scenario, agent, max_steps=1)

    assert result.achieved is True
    assert len(result.sanctions) == 1
    assert substrate.state.sanctions == result.sanctions
    assert result.sanctions[0].subject == "p1"
    assert result.sanctions[0].object == "resource-1"
    assert all("warning" in prompt for prompt in llm.user_prompts)
    assert all("legacy-value-that-must-not-be-used" not in prompt for prompt in llm.user_prompts)


class ScriptedLLM(LLM):
    def __init__(self):
        self.user_prompts = []

    def generate(self, system_prompt, user_prompt, tools, output_schema=None):
        self.user_prompts.append(user_prompt)
        if output_schema and "approved" in output_schema.get("properties", {}):
            output = {"approved": True, "rationale": "Approved."}
        else:
            output = {
                "action": {
                    "type": "use",
                    "actor": "p1",
                    "parameters": {"resource_id": "resource-1"},
                },
                "rationale": "Use the resource.",
            }
        return LLMResponse(content=None, tool_calls=[], structured_output=output)