from dataclasses import dataclass

@dataclass
class Action:
    type: str
    actor: str
    parameters: dict