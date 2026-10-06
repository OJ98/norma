from dataclasses import dataclass

from substrate import Action, ActionType

REASONER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    # The action space (A_t): the agent can only pick one of these.
                    "enum": [action_type.value for action_type in ActionType],
                },
                "actor": {
                    "type": "string",
                },
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
            "required": [
                "type",
                "actor",
                "parameters",
            ],
            "additionalProperties": False,
        },
        "rationale": {
            "type": "string",
        },
    },
    "required": [
        "action",
        "rationale",
    ],
    "additionalProperties": False,
}


@dataclass
class ReasonerProposal:
    action: Action
    rationale: str