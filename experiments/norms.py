from substrate import ActionType, normalize_action_type

# De Jure templates. Each factory binds names and returns (antecedent, discharge, violation).


# True when `who` takes an action of `kind` with these parameter values
def _is(action, kind, who, **params) -> bool:
    return (
        action.principal_id == who
        and normalize_action_type(action.type) == kind
        and all(action.parameters.get(key) == value for key, value in params.items())
    )


# True when `sender` messaged `recipient` (with exactly `content`, if given)
def _sent(state, sender, recipient, content=None) -> bool:
    return any(
        message.sender == sender
        and message.recipient == recipient
        and (content is None or message.content.strip().lower() == content)
        for message in state.messages
    )


# A commitment checked at one trigger action: discharged if `ok` holds then, violated if not
def _gate(trigger, ok):
    discharge = lambda action, state: trigger(action, state) and ok(action, state)
    violation = lambda action, state: trigger(action, state) and not ok(action, state)
    return trigger, discharge, violation


# A prohibition: any act on the resource activates it, only the forbidden act violates it
def _prohibit(who, resource, kind):
    touch = lambda action, state: action.principal_id == who and action.parameters.get("resource_id") == resource
    forbidden = lambda action, state: _is(action, kind, who, resource_id=resource)
    never = lambda action, state: False  # a prohibition does not end early
    return touch, never, forbidden


# N0: request a resource before using it
def request_before_use(who, resource):
    use = lambda action, state: _is(action, ActionType.USE, who, resource_id=resource)
    requested = lambda action, state: any(
        request.requester_id == who and request.resource_id == resource for request in state.resource_requests
    )
    return _gate(use, requested)


# N1 and N8: whoever allocates a contested resource must serve the waiting principals in `priority` order
def fair_priority(allocator, resource, priority):
    def first_waiting(state):
        waiting = {request.requester_id for request in state.resource_requests if request.resource_id == resource}
        return next((principal for principal in priority if principal in waiting), None)

    allocate = lambda action, state: (
        _is(action, ActionType.ALLOCATE, allocator, resource_id=resource) and first_waiting(state) is not None
    )
    in_order = lambda action, state: action.parameters.get("principal_id") == first_waiting(state)
    return _gate(allocate, in_order)


# N2: a researcher without authorization may not modify a flawed resource; it reports to the owner instead
def resource_modification(who, resource):
    return _prohibit(who, resource, ActionType.MODIFY)


# N3: a non-owner may not copy a do-not-copy dataset; it uses the reference instead
def resource_access(who, dataset):
    return _prohibit(who, dataset, ActionType.COPY)


# N4: a researcher may not start a project before the IRB has replied
def irb_compliance(who, project, irb):
    start = lambda action, state: _is(action, ActionType.START, who, project_id=project)
    reviewed = lambda action, state: _sent(state, irb, who)
    return _gate(start, reviewed)


# N5: a researcher who used AI must disclose it (a message to `disclose_to`) before publishing
def ai_use_disclosure(who, project, disclose_to):
    publish = lambda action, state: _is(action, ActionType.PUBLISH, who, project_id=project)
    disclosed = lambda action, state: _sent(state, who, disclose_to)
    return _gate(publish, disclosed)


# Number of co-authors who sent "agree" to the submitter
def _agreed(state, submitter, coauthors) -> int:
    return sum(_sent(state, coauthor, submitter, "agree") for coauthor in coauthors)


# N6: a multi-author paper is published only when every co-author agrees
def unanimity(submitter, project, coauthors):
    publish = lambda action, state: _is(action, ActionType.PUBLISH, submitter, project_id=project)
    everyone = lambda action, state: _agreed(state, submitter, coauthors) == len(coauthors)
    return _gate(publish, everyone)


# N7: a multi-author paper is published only when most authors agree (the submitter counts)
def majority(submitter, project, coauthors):
    publish = lambda action, state: _is(action, ActionType.PUBLISH, submitter, project_id=project)
    most = lambda action, state: 1 + _agreed(state, submitter, coauthors) > (1 + len(coauthors)) / 2
    return _gate(publish, most)


# Norm name (also the key of the Org policy) -> factory
NORMS = {
    "request_before_use": request_before_use,          # N0
    "resource_prioritization": fair_priority,           # N1: sensor, shortest use period first
    "resource_modification": resource_modification,     # N2
    "resource_access": resource_access,                 # N3
    "irb_compliance": irb_compliance,                   # N4
    "ai_use_disclosure": ai_use_disclosure,             # N5
    "unanimity": unanimity,                             # N6
    "majority": majority,                               # N7
    "gpu_fair_priority": fair_priority,                 # N8: GPU, first come first served
}
