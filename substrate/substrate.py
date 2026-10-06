from .model import Action, ActionResult, ActionType, Principal, Resource, ResourceType, Project, Message, ResourceRequest, SanctionDecision, SubstrateState, normalize_action_type
import uuid
from copy import deepcopy

class Substrate:

    def __init__(self):
        self.state = SubstrateState(
            principals=[],
            resources=[],
            projects=[],
            messages=[],
            resource_requests=[],
            sanctions=[],
        )

    def get_state(self) -> SubstrateState:
        return self.state

    # Simulate an action without modifying the actual state
    def simulate_action(self, action: Action):
        # Create a copy of the current state to simulate the action
        simulated_state = deepcopy(self.state)
        simulated_substrate = Substrate()
        simulated_substrate.state = simulated_state
        result = simulated_substrate.execute(action)

        if not result.success:
            raise ValueError(f"Action {action.type} failed: {result.message}")
        return simulated_state

    # Execute an action and update the state accordingly
    def execute(self, action: Action) -> ActionResult:
        action_type = normalize_action_type(action.type)

        # Call the appropriate handler based on the action type
        handlers = {
            ActionType.REQUEST: self.handle_request,
            ActionType.USE: self.handle_use,
            ActionType.MODIFY: self.handle_modify,
            ActionType.ALLOCATE: self.handle_allocate,
            ActionType.SEND: self.handle_send,
            ActionType.PUBLISH: self.handle_publish,
            ActionType.WAIT: self.handle_wait,
            ActionType.RELEASE: self.handle_release,
            ActionType.COPY: self.handle_copy,
            ActionType.START: self.handle_start,
        }

        handler = handlers.get(action_type)

        if handler is None:
            return ActionResult(success=False, message=f"Invalid action type: {action.type}")

        try:
            return handler(action)
        except Exception as e:
            return ActionResult(success=False, message=str(e))

    def apply_sanction(self, decision: SanctionDecision) -> ActionResult:
        self.state.sanctions.append(decision)
        return ActionResult(
            success=True,
            message=f"Sanction {decision.sanction.value} applied to {decision.subject}",
        )


    # Handler for the "request" action type
    def handle_request(self, action: Action) -> ActionResult:
        # Check if the required parameters are present
        resource_id = self._require_parameter(action, "resource_id")
        # Get the resource and principal objects
        resource = self._get_resource(resource_id)
        principal = self._get_principal(action.principal_id)

        # Generate a unique ID for the resource request
        resource_request_id = str(uuid.uuid4())

        self.state.resource_requests.append(ResourceRequest(id=resource_request_id, resource_id=resource_id, requester_id=principal.id))
        return ActionResult(success=True, message=f"Resource {resource_id} requested by principal {action.principal_id}")

    # Handler for the "allocate" action type
    def handle_allocate(self, action: Action) -> ActionResult:
        # Check if the required parameters are present
        resource_id = self._require_parameter(action, "resource_id")
        principal_id = self._require_parameter(action, "principal_id")
        # Get the resource and principal objects
        resource = self._get_resource(resource_id)
        principal = self._get_principal(principal_id)

        # Maybe we need an ownership check here, but for now we will just allocate the resource to the principal
        
        if resource.allocated_to != None:
            return ActionResult(success=False, message=f"Resource {resource_id} is already allocated to principal {resource.allocated_to}")

        resource.allocated_to = principal.id
        return ActionResult(success=True, message=f"Resource {resource_id} allocated to principal {principal.id}")


    # Handler for the "use" action type
    def handle_use(self, action: Action) -> ActionResult:
        # Check if the required parameters are present
        resource_id = self._require_parameter(action, "resource_id")
        # Get the resource and principal objects
        resource = self._get_resource(resource_id)
        principal = self._get_principal(action.principal_id)

        if resource.in_use_by != None:
            return ActionResult(success=False, message=f"Resource {resource_id} is already in use by principal {resource.in_use_by}")

        resource.in_use_by = principal.id
        return ActionResult(success=True, message=f"Resource {resource_id} is now in use by principal {principal.id}")

    def handle_wait(self, action: Action) -> ActionResult:
        self._get_principal(action.principal_id)
        return ActionResult(success=True, message=f"Principal {action.principal_id} is waiting")

    def handle_release(self, action: Action) -> ActionResult:
        if "project_id" in action.parameters:
            return self._release_project(action)  # withdraw a paper from a venue, or recuse from a review
        resource_id = self._require_parameter(action, "resource_id")
        resource = self._get_resource(resource_id)
        principal = self._get_principal(action.principal_id)

        if resource.in_use_by != principal.id:
            return ActionResult(success=False, message=f"Resource {resource_id} is not in use by principal {principal.id}")

        resource.in_use_by = None
        return ActionResult(success=True, message=f"Resource {resource_id} released by principal {principal.id}")

    # Copy a dataset into a new resource held by the actor
    def handle_copy(self, action: Action) -> ActionResult:
        resource_id = self._require_parameter(action, "resource_id")
        resource = self._get_resource(resource_id)
        principal = self._get_principal(action.principal_id)

        if resource.type != ResourceType.DATASET:
            return ActionResult(success=False, message=f"Resource {resource_id} is not a dataset and cannot be copied")

        copy_id = f"{resource_id}-copy-{principal.id}"
        if any(existing.id == copy_id for existing in self.state.resources):
            return ActionResult(success=False, message=f"Principal {principal.id} already holds a copy of {resource_id}")

        self.state.resources.append(Resource(copy_id, resource.type, allocated_to=principal.id, version=resource.version))
        return ActionResult(success=True, message=f"Resource {resource_id} copied to {copy_id} by principal {principal.id}")

    # Start a project (IRB review is a norm, not a precondition)
    def handle_start(self, action: Action) -> ActionResult:
        project_id = self._require_parameter(action, "project_id")
        project = self._get_project(project_id)
        self._get_principal(action.principal_id)

        if project.started:
            return ActionResult(success=False, message=f"Project {project_id} has already started")

        project.started = True
        return ActionResult(success=True, message=f"Project {project_id} started by principal {action.principal_id}")

    # Withdraw a project from the venue in recipient_id, or remove the actor from its authors (recusal)
    def _release_project(self, action: Action) -> ActionResult:
        project = self._get_project(action.parameters["project_id"])
        principal = self._get_principal(action.principal_id)
        venue = action.parameters.get("recipient_id")

        if venue:
            if venue not in project.venues:
                return ActionResult(success=False, message=f"Project {project.id} is not under review at {venue}")
            project.venues.remove(venue)
            return ActionResult(success=True, message=f"Project {project.id} withdrawn from {venue} by principal {principal.id}")

        if principal.id not in project.authors:
            return ActionResult(success=False, message=f"Principal {principal.id} is not on project {project.id}")
        project.authors.remove(principal.id)
        return ActionResult(success=True, message=f"Principal {principal.id} left project {project.id}")

    # Add principal_id to a project's authors
    def _add_author(self, action: Action) -> ActionResult:
        project = self._get_project(action.parameters["project_id"])
        author = self._get_principal(self._require_parameter(action, "principal_id"))

        if author.id in project.authors:
            return ActionResult(success=False, message=f"Principal {author.id} is already an author of {project.id}")
        project.authors.append(author.id)
        return ActionResult(success=True, message=f"Principal {author.id} added as an author of {project.id} by principal {action.principal_id}")

    # Handler for the "modify" action type
    def handle_modify(self, action: Action) -> ActionResult:
        if "project_id" in action.parameters:
            return self._add_author(action)  # modifying a project means adding an author
        # Check if the required parameters are present
        resource_id = self._require_parameter(action, "resource_id")
        # Get the resource and principal objects
        resource = self._get_resource(resource_id)
        principal = self._get_principal(action.principal_id)

        # Principal can only modify a resource if they are currently using it
        if resource.in_use_by != principal.id:
            return ActionResult(success=False, message=f"Resource {resource_id} is not in use by principal {principal.id}")

        resource.version += 1
        return ActionResult(success=True, message=f"Resource {resource_id} modified to version {resource.version} by principal {principal.id}")

    # Handler for the "send" action type
    def handle_send(self, action: Action) -> ActionResult:
        # Check if the required parameters are present
        message_id = self._require_parameter(action, "message_id")
        content = self._require_parameter(action, "content")
        recipient_id = self._require_parameter(action, "recipient_id")
        # Get the principal objects
        sender = self._get_principal(action.principal_id)
        recipient = self._get_principal(recipient_id)

        # A resource or project in the parameters travels with the message as an attachment
        attachment = action.parameters.get("project_id") or action.parameters.get("resource_id")
        message = Message(id=message_id, content=content, sender=sender.id, recipient=recipient.id, attachment=attachment)
        self.state.messages.append(message)
        return ActionResult(success=True, message=f"Message {message_id} sent from principal {sender.id} to principal {recipient.id}")


    # Handler for the "publish" action type
    def handle_publish(self, action: Action) -> ActionResult:
        if "project_id" in action.parameters:
            return self._handle_publish_project(action)
        elif "resource_id" in action.parameters:
            return self._handle_publish_resource(action)
        else:
            return ActionResult(success=False, message="Missing required parameter: project_id or resource_id")

    def _handle_publish_project(self, action: Action) -> ActionResult:
        project_id = self._require_parameter(action, "project_id")
        project = self._get_project(project_id)
        project.public = True
        venue = action.parameters.get("recipient_id")
        if venue and venue not in project.venues:
            project.venues.append(venue)  # submitting to a venue puts the paper under review there
        return ActionResult(success=True, message=f"Project {project_id} published by principal {action.principal_id}")
    
    def _handle_publish_resource(self, action: Action) -> ActionResult:
        resource_id = self._require_parameter(action, "resource_id")
        resource = self._get_resource(resource_id)
        if resource.type != ResourceType.DATASET:
            return ActionResult(success=False, message=f"Resource {resource_id} is not a dataset and cannot be published")
        resource.public = True
        return ActionResult(success=True, message=f"Resource {resource_id} published by principal {action.principal_id}")

    # Helper methods for common operations
    # Check if a parameter exists in the action's parameters and return its value, or raise an error if it doesn't exist
    def _require_parameter(self, action: Action, param_name: str):
        if param_name not in action.parameters:
            raise ValueError(f"Missing required parameter: {param_name}")
        return action.parameters[param_name]

    # Get a resource by its ID, or raise an error if it doesn't exist
    def _get_resource(self, resource_id: str) -> Resource:
        for resource in self.state.resources:
            if resource.id == resource_id:
                return resource
        raise ValueError(f"Resource with ID {resource_id} not found")

    # Get a project by its ID, or raise an error if it doesn't exist
    def _get_project(self, project_id: str) -> Project:
        for project in self.state.projects:
            if project.id == project_id:
                return project
        raise ValueError(f"Project with ID {project_id} not found")

    # Get a principal by its ID, or raise an error if it doesn't exist
    def _get_principal(self, principal_id: str) -> Principal:
        for principal in self.state.principals:
            if principal.id == principal_id:
                return principal
        raise ValueError(f"Principal with ID {principal_id} not found")
