import json
from dataclasses import asdict, dataclass
from enum import Enum

class ResourceType(Enum):
    COMPUTE = "compute"
    SENSOR = "sensor"
    DATASET = "dataset"

class ActionType(Enum):
    REQUEST = "request"
    USE = "use"
    MODIFY = "modify"
    ALLOCATE = "allocate"
    SEND = "send"
    PUBLISH = "publish"


class SanctionType(Enum):
    WARNING = "warning"

@dataclass
class Action:
    type: ActionType
    principal_id: str
    parameters: dict

@dataclass
class Principal:
    id:str

@dataclass
class Resource:
    id:str
    type:ResourceType
    allocated_to: str | None = None
    in_use_by: str | None = None
    version: int = 1
    public: bool = False

@dataclass
class Project:
    id: str
    public: bool = False

@dataclass
class Message:
    id: str
    content: str
    sender: str
    recipient: str

@dataclass
class ResourceRequest:
    id: str
    resource_id: str
    requester_id: str


@dataclass
class SanctionDecision:
    violation_id: int
    subject: str
    sanction: SanctionType
    object: str | None
    reason: str
    timestamp: int


@dataclass
class ViolationEvent:
    violation_id: int
    subject: str
    object: str | None
    norm_id: str

@dataclass
class SubstrateState:
    principals: list[Principal]
    resources: list[Resource]
    projects: list[Project]
    messages: list[Message]
    resource_requests: list[ResourceRequest]
    sanctions: list[SanctionDecision]


def serialize_state(state: SubstrateState | str) -> str:
    if isinstance(state, str):
        return state

    return json.dumps(
        asdict(state),
        default=lambda value: value.value if isinstance(value, Enum) else str(value),
        sort_keys=True,
    )

@dataclass
class ActionResult:
    success: bool
    message: str