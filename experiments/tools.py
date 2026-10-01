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
                "actiondict": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "principal_id": {"type": "string"},
                        "parameters": {
                            "type": "object",
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
