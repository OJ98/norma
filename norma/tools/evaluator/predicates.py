from typing import Callable
from substrate import Action, ActionType, ResourceType, SubstrateState

from .model import Predicate

# Checks if the action is of the expected type
def action_type(expected: ActionType) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        return action.type == expected
    return predicate

# Checks if the action has a specific parameter
def has_parameter(name: str) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        return name in action.parameters
    return predicate

# Check if requested resource is of the expected type
def resource_type(expected: ResourceType) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        resource_id = action.parameters.get("resource_id")
        if resource_id is None:
            return False
        return any(resource.id == resource_id and resource.type == expected for resource in state.resources)
    return predicate

# Checks if the resource is allocated to the user
def resource_allocated_to_user() -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        resource_id = action.parameters.get("resource_id")
        if resource_id is None:
            return False
        return any(resource.id == resource_id and resource.allocated_to == action.principal_id for resource in state.resources)
    return predicate

# Check if the resource is requested by the user
def resource_requested_by_user() -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        resource_id = action.parameters.get("resource_id")
        if resource_id is None:
            return False
        return any(request.resource_id == resource_id and request.requester_id == action.principal_id for request in state.resource_requests)
    return predicate

# Check if a parameter's value matches the expected value
def parameter_value(name: str, expected_value:object) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        return action.parameters.get(name) == expected_value
    return predicate


# Composition of predicates using logical AND
def all_of(*predicates: Predicate) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        return all(p(action, state) for p in predicates)
    return predicate

# Composition of predicates using logical OR
def any_of(*predicates: Predicate) -> Predicate:
    def predicate(action: Action, state: SubstrateState) -> bool:
        return any(p(action, state) for p in predicates)
    return predicate

# Composition of predicates using logical NOT
def negate(predicate: Predicate) -> Predicate:
    def negated(action: Action, state: SubstrateState) -> bool:
        return not predicate(action, state)
    return negated