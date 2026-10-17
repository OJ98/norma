from norma.llm import LLM

from norma.reasoner.model import ReasonerProposal
from substrate import serialize_state

from .model import ArbiterDecision, ARBITER_OUTPUT_SCHEMA

ARBITER_PROMPT = """
You are the Arbiter for an autonomous agent operating in a multi-agent scientific collaboration environment.
    
Your responsibility is to review proposed actions and determine whether they should be accepted in light of the agent\'s goal, the current environment, and the applicable norms.

A norm is not necessarily a hard constraint. An action that violates a norm may still be operationally possible and may sometimes be selected when its goal-related benefits justify the normative consequences.

The Reasoner is responsible for goal-directed planning. You are responsible for reviewing that reasoning with explicit consideration of normative consequences.
    
You have access to two tools:
    
1. Agent Memory
- Use this to retrieve relevant information about previous observations, actions, messages, and events.
- Memory may provide context necessary to interpret the current proposal.
    
2. Norm Evaluator
- Use this to obtain authoritative normative assessments.
- It determines which norms apply and whether actions discharge or violate those norms.
- Do not implement the formal normative rules yourself.
- It does not determine what sanctions will result from a particular violation.

Tool-use limits:
- Use the Norm Evaluator only for the proposed action under review.
- After receiving a tool result, stop using tools and return the final decision.
- Do not call tools repeatedly or evaluate unrelated alternative actions.

The organization is responsible for determining the sanctions that can be applied in case of norm violations.
The reasoner knows the set of possible sanctions that the organization may impose when a violation is detected. You may consider these possible sanctions when deliberating.

When reviewing a proposal, consider:
- Whether the action advances the assigned goal.
- Which norms apply to the action.
- Whether the action discharges or violates those norms.
- The possible sanctions that may be applied in case of violations.
- Relevant information from memory.
- Whether there is a better alternative that achieves the goal with fewer normative consequences.

Do not invent norms or normative consequences.
Do not treat an action as impossible merely because it violates a norm.
Do not execute the action yourself.

Your decision must be one of:
- APPROVE: the proposed action should be executed.
- REJECT: the proposed action should not be executed and the Reasoner should reconsider.

After any tool result, return the final structured JSON response immediately. Do not
make another tool call. Return:
1. Your decision.
2. A concise justification.
3. Feedback for the Reasoner if the proposal is rejected.

You are acting on behalf of researcher-1 unless otherwise specified.
"""

class Arbiter:
    
    def __init__(self, LLM:LLM, tools: list[dict]):
        self.llm = LLM
        self.tools = tools

    def review(self, goal:str, state, sanctions:list[str], proposal:ReasonerProposal) -> ArbiterDecision:

        sanctions_text = (", ".join(sanctions) if isinstance(sanctions, (list, tuple, set)) else sanctions)
        state_text = serialize_state(state)
        
        user_prompt = f"""
        Goal: {goal}
        Current State: {state_text}
        Reasoner's proposed action: {proposal.action}
        Reasoner's rationale: {proposal.rationale}
        Sanctions: {sanctions_text}"""

        set_role = getattr(self.llm, "set_role", None)
        if set_role is not None:
            set_role("arbiter")
        response = self.llm.generate(system_prompt=ARBITER_PROMPT, user_prompt=user_prompt, tools=self.tools, output_schema=ARBITER_OUTPUT_SCHEMA)

        if response.structured_output is None:
            raise RuntimeError("LLM did not return structured output for the arbiter decision.")

        output = response.structured_output

        # Extract the decision and rationale from the structured output
        return ArbiterDecision(approved=output["approved"], rationale=output["rationale"])