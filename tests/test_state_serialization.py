import json

from substrate import Principal, Resource, ResourceType, Substrate, serialize_state


def test_substrate_state_serializes_to_json_for_prompts():
    substrate = Substrate()
    substrate.state.principals.append(Principal("p1"))
    substrate.state.resources.append(Resource("gpu-1", ResourceType.COMPUTE))

    serialized = serialize_state(substrate.get_state())
    state = json.loads(serialized)

    assert state["principals"] == [{"id": "p1"}]
    assert state["resources"][0]["type"] == "compute"
    assert state["sanctions"] == []