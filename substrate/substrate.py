from .model import Action, ActionResult, ActionType, Principal, Resource, ResourceType, Project, Message, ResourceRequest, SubstrateState
import uuid

_ACTION_TYPE_ALIASES = {
    "send_message": "send",
    "request_resource": "request",
    "allocate_resource": "allocate",
    "use_resource": "use",
    "modify_resource": "modify",
    "publish_resource": "publish",
    "publish_project": "publish",
}


class Substrate:

    def __init__(self):
        self.state = SubstrateState(
            principals=[],
            resources=[],
            projects=[],
            messages=[],
            resource_requests=[]
        )

    def get_state(self) -> SubstrateState:
        return self.state

    def execute(self, action: Action) -> ActionResult:
        action_type = action.type
        if isinstance(action_type, str):
            normalized_type = _ACTION_TYPE_ALIASES.get(action_type, action_type)
            try:
                action_type = ActionType(normalized_type)
            except ValueError:
                action_type = normalized_type

        # Call the appropriate handler based on the action type
        handlers = {
            ActionType.REQUEST: self.handle_request,
            ActionType.USE: self.handle_use,
            ActionType.MODIFY: self.handle_modify,
            ActionType.ALLOCATE: self.handle_allocate,
            ActionType.SEND: self.handle_send,
            ActionType.PUBLISH: self.handle_publish
        }

        handler = handlers.get(action_type)

        if handler is None:
            return ActionResult(success=False, message=f"Invalid action type: {action.type}")

        try:
            return handler(action)
        except Exception as e:
            return ActionResult(success=False, message=str(e))


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

    # Handler for the "modify" action type
    def handle_modify(self, action: Action) -> ActionResult:
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

        message = Message(id=message_id, content=content, sender=sender.id, recipient=recipient.id)
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
