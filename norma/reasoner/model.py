from dataclasses import dataclass

from substrate import Action

REASONER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                },
                "actor": {
                    "type": "string",
                },
                "parameters": {
                    "type": "object",
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