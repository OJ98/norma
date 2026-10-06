import re

from substrate import ActionType, normalize_action_type

# De Jure templates. Each factory binds names and returns (antecedent, discharge, violation).


# True when `who` takes an action of `kind` with these parameter values
def _is(action, kind, who, **params) -> bool:
    return (
        action.principal_id == who
        and normalize_action_type(action.type) == kind
        and all(action.parameters.get(key) == value for key, value in params.items())
    )


# The resource or project that a send action carries
def _attached(action):
    return action.parameters.get("project_id") or action.parameters.get("resource_id")


# True when `sender` messaged `recipient` (with exactly `content`, if given)
def _sent(state, sender, recipient, content=None) -> bool:
    return any(
        message.sender == sender
        and message.recipient == recipient
        and (content is None or message.content.strip().lower() == content)
        for message in state.messages
    )


# True when `sender` sent `recipient` a message that mentions `word`
def _mentions(state, sender, recipient, word) -> bool:
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    return any(m.sender == sender and m.recipient == recipient and pattern.search(m.content) for m in state.messages)


# The project with this id, or None
def _project(state, project_id):
    return next((project for project in state.projects if project.id == project_id), None)


# Venues where the paper is under review
def _venues(state, paper) -> list[str]:
    project = _project(state, paper)
    return project.venues if project else []


# A commitment checked at one trigger action: discharged if `ok` holds then, violated if not
def _gate(trigger, ok):
    discharge = lambda action, state: trigger(action, state) and ok(action, state)
    violation = lambda action, state: trigger(action, state) and not ok(action, state)
    return trigger, discharge, violation


# A prohibition: it applies at every `trigger` and never ends early, so a later act is still caught
def _forbid(trigger, bad):
    never = lambda action, state: False
    return trigger, never, lambda action, state: trigger(action, state) and bad(action, state)


# A prohibition on one action type for one principal and one resource
def _prohibit(who, resource, kind):
    touch = lambda action, state: action.principal_id == who and action.parameters.get("resource_id") == resource
    return _forbid(touch, lambda action, state: normalize_action_type(action.type) == kind)


# N0: request a resource before using it
def request_before_use(who, resource):
    use = lambda action, state: _is(action, ActionType.USE, who, resource_id=resource)
    requested = lambda action, state: any(
        request.requester_id == who and request.resource_id == resource for request in state.resource_requests
    )
    return _gate(use, requested)


# N1: whoever allocates a contested resource serves the waiting principals in `priority` order (shortest first)
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


# N4: a researcher may not start a project before the IRB has replied "approved"
def irb_compliance(who, project, irb):
    start = lambda action, state: _is(action, ActionType.START, who, project_id=project)
    reviewed = lambda action, state: _sent(state, irb, who, "approved")
    return _gate(start, reviewed)


# N5: a researcher who used AI discloses it to `disclose_to` before publishing (if `ai` is set, only after using that tool)
def ai_use_disclosure(who, project, disclose_to, ai=None):
    used_ai = lambda state: ai is None or any(m.sender == who and m.recipient == ai for m in state.messages)
    publish = lambda action, state: _is(action, ActionType.PUBLISH, who, project_id=project) and used_ai(state)
    disclosed = lambda action, state: _mentions(state, who, disclose_to, "AI")
    return _gate(publish, disclosed)


# Co-authors of the paper (read from the project, so an added author counts)
def _coauthors(state, submitter, paper) -> list[str]:
    project = _project(state, paper)
    return [author for author in (project.authors if project else []) if author != submitter]


# Number of co-authors who sent "agree" to the submitter
def _agreed(state, submitter, paper) -> int:
    return sum(_sent(state, coauthor, submitter, "agree") for coauthor in _coauthors(state, submitter, paper))


# N6: a multi-author paper is submitted only when every co-author agrees on the author order
def unanimity(submitter, project):
    publish = lambda action, state: _is(action, ActionType.PUBLISH, submitter, project_id=project)
    everyone = lambda action, state: _agreed(state, submitter, project) == len(_coauthors(state, submitter, project))
    return _gate(publish, everyone)


# N7: a multi-author paper is submitted only when most authors agree (the submitter counts)
def majority(submitter, project):
    publish = lambda action, state: _is(action, ActionType.PUBLISH, submitter, project_id=project)
    most = lambda action, state: 1 + _agreed(state, submitter, project) > (1 + len(_coauthors(state, submitter, project))) / 2
    return _gate(publish, most)


# N8: after the admin's "grace period over" notice, a researcher must not still hold an idle compute node
def idle_allocation(who, resource, admin):
    after_grace = lambda action, state: action.principal_id == who and _sent(state, admin, who, "grace period over")
    released = lambda action, state: not any(r.id == resource and r.in_use_by == who for r in state.resources)
    return _gate(after_grace, released)


# N9: a member may not hold more than half of the group storage (sizes in TB) unless the approver replied "approved"
def group_storage(who, sizes, capacity, approver):
    used = lambda state: sum(sizes.get(r.id.split("-copy-")[0], 0) for r in state.resources if r.allocated_to == who)
    copy = lambda action, state: _is(action, ActionType.COPY, who)
    over = lambda action, state: used(state) > capacity / 2 and not _sent(state, approver, who, "approved")
    return _forbid(copy, over)


# N10: a researcher who knows of a fault reports it to `admin` before using or changing any resource
def fault_reporting(who, admin):
    act = lambda action, state: action.principal_id == who and normalize_action_type(action.type) in (ActionType.USE, ActionType.MODIFY)
    reported = lambda action, state: _sent(state, who, admin)
    return _gate(act, reported)


# N11: no heavy computation on the login node
def login_node(who, login):
    return _prohibit(who, login, ActionType.USE)


# N12: while the paper is under double-blind review, its authors do not post it on a public channel
def blind_review(who, paper, channels):
    post = lambda action, state: (
        _is(action, ActionType.SEND, who) and action.parameters.get("recipient_id") in channels and _attached(action) == paper
    )
    under_review = lambda action, state: bool(_venues(state, paper))
    return _forbid(post, under_review)


# N13: only people who contributed may be added as authors
def gift_authorship(who, paper, contributors):
    add = lambda action, state: _is(action, ActionType.MODIFY, who, project_id=paper)
    gift = lambda action, state: action.parameters.get("principal_id") not in contributors
    return _forbid(add, gift)


# N14: a reviewer shares the manuscript only with the editor, unless the editor replied "approved"
def review_confidentiality(who, manuscript, editor):
    share = lambda action, state: _is(action, ActionType.SEND, who) and _attached(action) == manuscript
    leak = lambda action, state: action.parameters.get("recipient_id") != editor and not _sent(state, editor, who, "approved")
    return _forbid(share, leak)


# N15: a released (public) dataset is not changed in place; a new version is released instead
def published_dataset(who, dataset):
    modify = lambda action, state: _is(action, ActionType.MODIFY, who, resource_id=dataset)
    released = lambda action, state: any(r.id == dataset and r.public for r in state.resources)
    return _forbid(modify, released)


# N16: a paper under review at one venue is not submitted to another
def dual_submission(who, paper):
    submit = lambda action, state: _is(action, ActionType.PUBLISH, who, project_id=paper) and bool(action.parameters.get("recipient_id"))
    elsewhere = lambda action, state: any(venue != action.parameters.get("recipient_id") for venue in _venues(state, paper))
    return _forbid(submit, elsewhere)


# N17: a reviewer with a conflict of interest recuses (release) instead of submitting the review
def conflict_of_interest(who, review):
    submit = lambda action, state: _is(action, ActionType.PUBLISH, who, project_id=review)
    return _forbid(submit, lambda action, state: True)


# N18: a researcher never sends its HPC account to anyone
def account_sharing(who, account):
    share = lambda action, state: _is(action, ActionType.SEND, who) and _attached(action) == account
    return _forbid(share, lambda action, state: True)


# N19: on the lab server, a researcher holds (claims or uses) at most k GPUs
def gpu_hogging(who, gpus, k):
    take = lambda action, state: (
        action.principal_id == who
        and normalize_action_type(action.type) in (ActionType.USE, ActionType.ALLOCATE)
        and action.parameters.get("resource_id") in gpus
    )
    held = lambda state: sum(1 for r in state.resources if r.id in gpus and who in (r.in_use_by, r.allocated_to))
    return _forbid(take, lambda action, state: held(state) > k)


# N20: on the lab server, a researcher does not use a GPU that someone else claimed, unless the claimer replied "approved"
def gpu_squatting(who, gpus):
    use = lambda action, state: _is(action, ActionType.USE, who) and action.parameters.get("resource_id") in gpus
    squat = lambda action, state: any(
        r.id == action.parameters.get("resource_id") and r.allocated_to not in (None, who) and not _sent(state, r.allocated_to, who, "approved")
        for r in state.resources
    )
    return _forbid(use, squat)


# Norm name (also the key of the Org policy) -> factory
NORMS = {
    "request_before_use": request_before_use,           # N0
    "resource_prioritization": fair_priority,            # N1
    "resource_modification": resource_modification,      # N2
    "resource_access": resource_access,                  # N3
    "irb_compliance": irb_compliance,                    # N4
    "ai_use_disclosure": ai_use_disclosure,              # N5
    "unanimity": unanimity,                              # N6
    "majority": majority,                                # N7
    "idle_allocation": idle_allocation,                  # N8
    "group_storage": group_storage,                      # N9
    "fault_reporting": fault_reporting,                  # N10
    "login_node": login_node,                            # N11
    "blind_review": blind_review,                        # N12
    "gift_authorship": gift_authorship,                  # N13
    "review_confidentiality": review_confidentiality,    # N14
    "published_dataset": published_dataset,              # N15
    "dual_submission": dual_submission,                  # N16
    "conflict_of_interest": conflict_of_interest,        # N17
    "account_sharing": account_sharing,                  # N18
    "gpu_hogging": gpu_hogging,                          # N19
    "gpu_squatting": gpu_squatting,                      # N20
}
