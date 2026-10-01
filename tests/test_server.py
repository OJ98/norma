from types import SimpleNamespace

import pytest

pytest.importorskip("mcp.server.fastmcp")

from norma.tools.evaluator.model import NormStatus
from norma.tools.server import create_server
from substrate import ActionType


class FakeEvaluator:
    def evaluate_action(self, action):
        return SimpleNamespace(
            action=action,
            next_state=SimpleNamespace(dict=lambda: {"state": "next"}),
            evaluations=[SimpleNamespace(instance_id="instance-1", status=NormStatus.DISCHARGED)],
        )


class FakeMemory:
    def __init__(self):
        self.entries = [SimpleNamespace(id="mem-1", content="alpha"), SimpleNamespace(id="mem-2", content="beta")]

    def store(self, content):
        entry = SimpleNamespace(id="mem-3", content=content)
        self.entries.append(entry)
        return entry

    def retrieve(self, query, k=5):
        return self.entries[:k]


def _find_tool(server, tool_name):
    manager = getattr(server, "_tool_manager", None) or getattr(server, "tool_manager", None)
    assert manager is not None

    if hasattr(manager, "list_tools"):
        return next((tool for tool in manager.list_tools() if getattr(tool, "name", None) == tool_name), None)

    tool_map = getattr(manager, "_tools", None) or getattr(manager, "tools", {})
    if isinstance(tool_map, dict):
        return next((tool for tool in tool_map.values() if getattr(tool, "name", None) == tool_name), None)

    return None


def test_create_server_registers_tool_functions():
    server = create_server(FakeEvaluator(), FakeMemory())

    tool_names = {
        getattr(tool, "name", None)
        for tool in (getattr(server, "_tool_manager", None).list_tools() if hasattr(getattr(server, "_tool_manager", None), "list_tools") else [])
    }
    if not tool_names:
        manager = getattr(server, "_tool_manager", None) or getattr(server, "tool_manager", None)
        tool_map = getattr(manager, "_tools", None) or getattr(manager, "tools", {})
        tool_names = {getattr(tool, "name", None) for tool in tool_map.values()}

    assert {"store_memory", "retrieve_memory", "evaluate_action"}.issubset(tool_names)

    store_tool = _find_tool(server, "store_memory")
    assert store_tool is not None
    store_fn = getattr(store_tool, "fn", store_tool)
    assert callable(store_fn)
    assert store_fn("hello") == {"entry_id": "mem-3", "content": "hello"}

    evaluate_tool = _find_tool(server, "evaluate_action")
    assert evaluate_tool is not None
    evaluate_fn = getattr(evaluate_tool, "fn", evaluate_tool)
    assert callable(evaluate_fn)

    result = evaluate_fn({
        "type": ActionType.SEND.value,
        "principal_id": "p1",
        "parameters": {"message_id": "msg-1"},
    })

    assert result["action"]["principal_id"] == "p1"
    assert result["next_state"] == {"state": "next"}
    assert result["evaluations"][0]["status"] == NormStatus.DISCHARGED.value