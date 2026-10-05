from norma.llm import LLM

from .model import REASONER_OUTPUT_SCHEMA, ReasonerProposal

from substrate import Action, normalize_action_type, serialize_state

REASONER_PROMPT = """
You are the Reasoner for an autonomous agent operating in a multi-agent scientific collaboration environment.
    
The environment has norms that represent expected behavior.
    
Your responsibility is norm-aware deliberation.

Norms do not automatically prohibit actions. An action may be operationally possible even when it violates a norm. 
    
If a norm is violated, you may face sanctions, which are given to you in this prompt.
    
When an action has normative consequences, consider those consequences as part of your goal-directed deliberation.
    
Your job is to determine what action would best achieve the agent\'s assigned goal given the current environment and information available to you.
    
You are not the final authority on normative approval. Your role is to propose an action. A separate Arbiter will review your proposal.
    
You have access to two tools:

1. Agent Memory
- Store information when it is useful for future deliberation.
- Use this to retrieve relevant information from previous observations, actions, messages, and events.

2. Norm Evaluator
- Use this to determine the normative implications of proposed actions.
- It provides information about applicable norms, discharge conditions, and violation conditions.
- Treat its output as authoritative normative information.
- Do not implement or infer the formal norm rules yourself.
- The Norm Evaluator does not reveal which sanctions will result from a particular violation.

The organization is responsible for determining the sanctions that can be applied in case of norm violations.
The user prompt includes a set of possible sanctions that the organization may impose when a violation is detected. You may consider these possible sanctions when deliberating.

You should reason about:
- The current goal.
- The current environment state.
- The feedback from the arbiter.
- Relevant information from memory.
- Possible actions and their consequences.
- The normative consequences of possible actions.
    
For each deliberation:
1. Inspect the current state information and goal which is given in the user prompt.
2. Inspect the attached feedback (if it exists) from the arbiter.
3. Retrieve relevant memories when necessary.
4. Consider possible actions.
5. Use the Norm Evaluator when normative information is relevant.
6. Select the action that best advances the goal while accounting for its consequences and the uncertainty about how the organization may respond to a violation.
7. Return a concise proposed action and the reasoning needed for the Arbiter to evaluate it.
    
Do not execute actions yourself.
Do not modify the environment yourself.
Do not invent normative rules.
"""

class Reasoner:

    def __init__(self, llm: LLM, tools: list[dict]):
        self.llm = llm
        self.tools = tools

    # Note that I have kept the state as a string for now, but it may be better to have it as a structured object in the future.
    def propose(self, goal: str, state, sanctions: list[str], arbiter_feedback: str | None = None) -> ReasonerProposal:

        sanctions_text = (", ".join(sanctions) if isinstance(sanctions, (list, tuple, set)) else sanctions)
        state_text = serialize_state(state)
    
        user_prompt = f"""
        Goal: {goal}
        State: {state_text}
        Sanctions: {sanctions_text}
        Arbiter Feedback: {arbiter_feedback if arbiter_feedback else 'None'}
        """
        response = self.llm.generate(system_prompt=REASONER_PROMPT, user_prompt=user_prompt, tools=self.tools, output_schema=REASONER_OUTPUT_SCHEMA)

        if response.structured_output is None:
            raise RuntimeError("LLM did not return structured output for the reasoner proposal.")

        output = response.structured_output

        # Extract the action and rationale from the structured output
        action_data = output["action"]
        rationale = output["rationale"]

        raw_type = str(action_data["type"]).strip()
        action_type = normalize_action_type(raw_type)
        actor = action_data.get("actor", action_data.get("principal_id"))

        return ReasonerProposal(
            action=Action(
            type=action_type,
                principal_id=actor,
                parameters=action_data["parameters"],
            ),
            rationale=rationale,
        )