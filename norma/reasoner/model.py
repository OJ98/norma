from dataclasses import dataclass, field

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
                        "resource_id": {"type": ["string", "null"]},
                        "principal_id": {"type": ["string", "null"]},
                        "project_id": {"type": ["string", "null"]},
                        "message_id": {"type": ["string", "null"]},
                        "content": {"type": ["string", "null"]},
                        "recipient_id": {"type": ["string", "null"]},
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
        "candidate_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [action_type.value for action_type in ActionType],
                    },
                    "actor": {"type": "string"},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "resource_id": {"type": ["string", "null"]},
                            "principal_id": {"type": ["string", "null"]},
                            "project_id": {"type": ["string", "null"]},
                            "message_id": {"type": ["string", "null"]},
                            "content": {"type": ["string", "null"]},
                            "recipient_id": {"type": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                    "notes": {"type": "string"},
                },
                "additionalProperties": False,
            },
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
    candidate_actions: list[dict] = field(default_factory=list)
