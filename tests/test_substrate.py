import unittest

from substrate.model import Action, ActionType, Principal, Project, Resource, ResourceType
from substrate.substrate import Substrate


class TestSubstrate(unittest.TestCase):
    def setUp(self):
        self.substrate = Substrate()
        self.substrate.state.principals.extend([Principal("p1"), Principal("p2")])
        self.substrate.state.resources.extend([
            Resource("dataset-1", ResourceType.DATASET),
            Resource("compute-1", ResourceType.COMPUTE),
        ])
        self.substrate.state.projects.append(Project("project-1"))

    def test_request_updates_state(self):
        result = self.substrate.execute(
            Action(ActionType.REQUEST, "p1", {"resource_id": "dataset-1"})
        )

        self.assertTrue(result.success)
        self.assertEqual(len(self.substrate.state.resource_requests), 1)
        request = self.substrate.state.resource_requests[0]
        self.assertTrue(request.id)
        self.assertEqual(request.resource_id, "dataset-1")
        self.assertEqual(request.requester_id, "p1")

    def test_allocate_updates_resource_and_rejects_duplicate(self):
        action = Action(
            ActionType.ALLOCATE,
            "p1",
            {"resource_id": "compute-1", "principal_id": "p2"},
        )

        result = self.substrate.execute(action)
        duplicate_result = self.substrate.execute(action)

        self.assertTrue(result.success)
        self.assertFalse(duplicate_result.success)
        self.assertEqual(self.substrate.state.resources[1].allocated_to, "p2")

    def test_use_and_modify_update_resource(self):
        use_result = self.substrate.execute(
            Action(ActionType.USE, "p1", {"resource_id": "dataset-1"})
        )
        modify_result = self.substrate.execute(
            Action(ActionType.MODIFY, "p1", {"resource_id": "dataset-1"})
        )

        resource = self.substrate.state.resources[0]
        self.assertTrue(use_result.success)
        self.assertTrue(modify_result.success)
        self.assertEqual(resource.in_use_by, "p1")
        self.assertEqual(resource.version, 2)

    def test_modify_requires_current_user(self):
        self.substrate.state.resources[0].in_use_by = "p2"

        result = self.substrate.execute(
            Action(ActionType.MODIFY, "p1", {"resource_id": "dataset-1"})
        )

        self.assertFalse(result.success)
        self.assertEqual(self.substrate.state.resources[0].version, 1)

    def test_send_adds_message(self):
        result = self.substrate.execute(
            Action(
                ActionType.SEND,
                "p1",
                {
                    "message_id": "message-1",
                    "content": "hello",
                    "recipient_id": "p2",
                },
            )
        )

        self.assertTrue(result.success)
        self.assertEqual(len(self.substrate.state.messages), 1)
        self.assertEqual(self.substrate.state.messages[0].sender, "p1")
        self.assertEqual(self.substrate.state.messages[0].recipient, "p2")

    def test_publish_project_and_dataset(self):
        project_result = self.substrate.execute(
            Action(ActionType.PUBLISH, "p1", {"project_id": "project-1"})
        )
        resource_result = self.substrate.execute(
            Action(ActionType.PUBLISH, "p1", {"resource_id": "dataset-1"})
        )

        self.assertTrue(project_result.success)
        self.assertTrue(resource_result.success)
        self.assertTrue(self.substrate.state.projects[0].public)
        self.assertTrue(self.substrate.state.resources[0].public)

    def test_publish_rejects_non_dataset_resource(self):
        result = self.substrate.execute(
            Action(ActionType.PUBLISH, "p1", {"resource_id": "compute-1"})
        )

        self.assertFalse(result.success)
        self.assertFalse(self.substrate.state.resources[1].public)

    def test_missing_parameter_returns_failure(self):
        result = self.substrate.execute(Action(ActionType.USE, "p1", {}))

        self.assertFalse(result.success)
        self.assertIn("Missing required parameter", result.message)

    def test_invalid_action_type_returns_failure(self):
        result = self.substrate.execute(Action("invalid", "p1", {}))

        self.assertFalse(result.success)
        self.assertIn("Invalid action type", result.message)


if __name__ == "__main__":
    unittest.main()
