# The Reasoner receives all tools; the Arbiter uses the filtered list below so
# it can inspect norms without changing the agent's memory.
EXPERIMENT_TOOLS = [
    {
        "name": "store_memory",
        "description": "Store a useful observation for later deliberation.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "retrieve_memory",
        "description": "Retrieve memories relevant to a query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluate_action",
        "description": "Evaluate an action against the active norms and projected state.",
        "input_schema": {
            "type": "object",
            "properties": {
                # `principal_id` identifies the actor; action-specific values
                # belong in `parameters` and must use these exact names.
                "actiondict": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "principal_id": {"type": "string"},
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "resource_id": {"type": "string"},
                                "principal_id": {"type": "string"},
                                "project_id": {"type": "string"},
                                "message_id": {"type": "string"},
                                "content": {"type": "string"},
                                "recipient_id": {"type": "string"},
                            },
                            "additionalProperties": False,
                        },
                    },
                    "required": ["type", "principal_id"],
                    "additionalProperties": False,
                },
            },
            "required": ["actiondict"],
            "additionalProperties": False,
        },
    },
]

ARBITER_TOOLS = [tool for tool in EXPERIMENT_TOOLS if tool["name"] != "store_memory"]
