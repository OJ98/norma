import json
from dataclasses import asdict, dataclass
from enum import Enum

class ResourceType(Enum):
    COMPUTE = "compute"
    SENSOR = "sensor"
    DATASET = "dataset"

class ActionType(Enum):
    # These values are the canonical forms used by dispatch and predicates.
    REQUEST = "request"
    USE = "use"
    MODIFY = "modify"
    ALLOCATE = "allocate"
    SEND = "send"
    PUBLISH = "publish"
    WAIT = "wait"
    RELEASE = "release"
    COPY = "copy"
    START = "start"


class SanctionType(Enum):
    WARNING = "warning"
    ESCALATION_TO_ORG = "escalation to Org"
    LOSS_OF_RESOURCE_ACCESS = "loss of resource access"
    INABILITY_TO_REQUEST_RESOURCE = "inability to request another resource until authorized"
    ESCALATION_TO_RESOURCE_OWNER_AND_ORG = "escalation to resource owner and Org"
    SUSPENSION_OF_PROJECT = "suspension of project pending review"
    PAPER_WITHDRAWAL = "paper withdrawal"
    REPUTATION_LOSS = "reputation loss"
    EXPULSION = "expulsion"
    SANCTION_ALL_AUTHORS = "sanction all authors"

@dataclass
class Action:
    # Allocation targets use parameters["principal_id"]; the actor is the
    # principal_id field on the action itself.
    type: ActionType
    principal_id: str
    parameters: dict


_ACTION_TYPE_ALIASES = {
    "send_message": ActionType.SEND,
    "request_resource": ActionType.REQUEST,
    "allocate_resource": ActionType.ALLOCATE,
    "use_resource": ActionType.USE,
    "modify_resource": ActionType.MODIFY,
    "publish_resource": ActionType.PUBLISH,
    "publish_project": ActionType.PUBLISH,
    "copy_resource": ActionType.COPY,
    "start_project": ActionType.START,
}


def normalize_action_type(action_type: ActionType | str) -> ActionType | str:
    # Keep old experiment/LLM spellings interoperable with canonical enums.
    if isinstance(action_type, ActionType):
        return action_type
    try:
        return ActionType(_ACTION_TYPE_ALIASES.get(action_type, action_type))
    except ValueError:
        return action_type

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
    started: bool = False

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
    # event_type and timestamp let Org policies distinguish when and how a
    # violation occurred without introducing norm-instance state machines.
    violation_id: int
    subject: str
    object: str | None
    norm_id: str
    event_type: str | None = None
    timestamp: int | None = None

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