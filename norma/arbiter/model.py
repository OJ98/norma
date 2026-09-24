from dataclasses import dataclass

ARBITER_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {
            "type": "boolean",
        },
        "rationale": {
            "type": "string",
        },
    },
    "required": [
        "approved",
        "rationale",
    ],
    "additionalProperties": False,
}

@dataclass
class ArbiterDecision:
    approved: bool
    rationale: str