from dataclasses import asdict

from mcp.server.fastmcp import FastMCP

from norma.tools.evaluator.evaluator import NormEvaluator
from norma.tools.memory.store import AgentMemory

from substrate import Action, ActionType


def _state_to_dict(state) -> dict:
    if hasattr(state, "dict"):
        return state.dict()
    return asdict(state)


# Create a FastMCP server with the NormEvaluator and AgentMemory tools.
def create_server(memory: AgentMemory, evaluator: NormEvaluator) -> FastMCP:
    mcp = FastMCP("norma-tools")
    
    # Memory Tools
    @mcp.tool()
    def store_memory(content: str) -> dict:
        entry = memory.store(content)
        return {"entry_id": entry.id, "content": entry.content}

    @mcp.tool()
    def retrieve_memory(query: str, k: int = 5) -> dict:
        entries = memory.retrieve(query, k)
        return {"entries": [{"entry_id": entry.id, "content": entry.content} for entry in entries]}

    # Evaluator Tools
    @mcp.tool()
    def evaluate_action(actiondict: dict) -> dict:
        action_type = actiondict["type"]
        try:
            action_type = ActionType(action_type)
        except ValueError:
            pass
        action = Action(
            type=action_type,
            principal_id=actiondict["principal_id"],
            parameters=actiondict.get("parameters", {}),
        )
        
        result = evaluator.evaluate_action(action)
        return {
            "action": {
                "type": result.action.type,
                "principal_id": result.action.principal_id,
                "parameters": result.action.parameters,
            },
            "next_state": _state_to_dict(result.next_state),
            "evaluations": [
                {"instance_id": eval.instance_id, "status": eval.status.value}
                for eval in result.evaluations
            ],
        }
    return mcp