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
        "decision": {
            "type": "string",
            "enum": ["APPROVE", "REJECT"],
        },
        "feedback": {
            "type": ["string", "null"],
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
