from experiments.tools import ARBITER_TOOLS, EXPERIMENT_TOOLS


def test_arbiter_cannot_write_memory_but_reasoner_can():
    assert "store_memory" in {tool["name"] for tool in EXPERIMENT_TOOLS}
    assert "store_memory" not in {tool["name"] for tool in ARBITER_TOOLS}


def test_evaluate_action_schema_lists_supported_parameters():
    evaluate_action = next(tool for tool in EXPERIMENT_TOOLS if tool["name"] == "evaluate_action")
    parameters = evaluate_action["input_schema"]["properties"]["actiondict"]["properties"]["parameters"]

    assert set(parameters["properties"]) == {
        "resource_id",
        "principal_id",
        "project_id",
        "message_id",
        "content",
        "recipient_id",
    }
    assert parameters["additionalProperties"] is False