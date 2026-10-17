import json
from types import SimpleNamespace

import pytest

from norma.llm.openai_compatible import OpenAICompatibleLLM


SCHEMA = {
    "type": "object",
    "properties": {"approved": {"type": "boolean"}, "rationale": {"type": "string"}},
    "required": ["approved", "rationale"],
    "additionalProperties": False,
}


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return next(self.responses)


def response(content, *, tool_calls=None, finish_reason="stop", usage=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [], model_dump=lambda **_: {"role": "assistant", "content": content, "tool_calls": tool_calls} if tool_calls else {"role": "assistant", "content": content})
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)], usage=usage)


def llm_for(provider, responses):
    llm = OpenAICompatibleLLM.__new__(OpenAICompatibleLLM)
    llm.provider = provider
    llm.model = "test-model"
    llm.max_tokens = 128
    llm.tool_executor = None
    llm.tool_result_logger = None
    fake = FakeCompletions(responses)
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=fake))
    return llm, fake


@pytest.mark.parametrize("provider", ["openai", "deepseek"])
def test_structured_response_is_parsed_and_validated(provider):
    llm, fake = llm_for(provider, [response('{"approved": true, "rationale": "ok"}', usage=SimpleNamespace(prompt_tokens=12, completion_tokens=4, total_tokens=16))])
    result = llm.generate("sys", "user", [], SCHEMA)
    assert result.structured_output == {"approved": True, "rationale": "ok"}
    assert result.usage == {"input_tokens": 12, "output_tokens": 4, "total_tokens": 16}
    assert fake.requests[0]["response_format"]["type"] == ("json_schema" if provider == "openai" else "json_object")


def test_invalid_schema_and_malformed_json_raise_clear_errors():
    llm, _ = llm_for("deepseek", [response('{"approved": "yes"}')])
    with pytest.raises(RuntimeError, match="does not match.*schema"):
        llm.generate("sys", "user", [], SCHEMA)
    llm, _ = llm_for("deepseek", [response("not json")])
    with pytest.raises(RuntimeError, match="parse structured output"):
        llm.generate("sys", "user", [], SCHEMA)


def test_tool_call_maps_mcp_schema_and_preserves_callback_execution():
    call = SimpleNamespace(id="call-1", function=SimpleNamespace(name="retrieve_memory", arguments='{"query":"GPU"}'))
    llm, fake = llm_for("openai", [response(None, tool_calls=[call]), response('{"approved": true, "rationale": "done"}')])
    executed = []
    llm.tool_executor = lambda name, arguments: executed.append((name, arguments)) or {"entries": []}
    logged = []
    llm.tool_result_logger = lambda tool, result: logged.append((tool.id, result))
    result = llm.generate("sys", "user", [{"name": "retrieve_memory", "description": "Retrieve", "input_schema": {"type": "object"}}], SCHEMA)
    assert result.structured_output["approved"] is True
    assert executed == [("retrieve_memory", {"query": "GPU"})]
    assert logged[0][0] == "call-1"
    assert fake.requests[0]["tools"][0]["function"]["parameters"] == {"type": "object"}
    assert fake.requests[1]["messages"][-1]["role"] == "tool"


def test_truncation_and_usage_absence_are_reported_or_preserved():
    llm, _ = llm_for("openai", [response('{"approved": true, "rationale": "ok"}', finish_reason="length")])
    with pytest.raises(RuntimeError, match="truncated"):
        llm.generate("sys", "user", [], SCHEMA)
    llm, _ = llm_for("openai", [response('{"approved": true, "rationale": "ok"}')])
    assert llm.generate("sys", "user", [], SCHEMA).usage is None


def test_missing_credentials_and_provider_configuration(monkeypatch):
    from norma.llm.config import configured_max_tokens, configured_provider

    monkeypatch.setenv("NORMA_PROVIDER", "deepseek")
    monkeypatch.delenv("NORMA_MODEL", raising=False)
    assert configured_provider() == ("deepseek", "deepseek-chat")
    monkeypatch.setenv("NORMA_MAX_TOKENS", "8192")
    assert configured_max_tokens() == 8192
    monkeypatch.setenv("NORMA_MAX_TOKENS", "invalid")
    with pytest.raises(ValueError, match="NORMA_MAX_TOKENS"):
        configured_max_tokens()
    monkeypatch.delenv("NORMA_MAX_TOKENS")
    assert configured_max_tokens() == 4096
    monkeypatch.setenv("NORMA_PROVIDER", "invalid")
    with pytest.raises(ValueError, match="Unsupported NORMA_PROVIDER"):
        configured_provider()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        OpenAICompatibleLLM(model="test", provider="deepseek")


def test_provider_api_errors_are_reported_without_retry():
    class ProviderError(Exception):
        pass

    class BrokenCompletions:
        calls = 0

        def create(self, **kwargs):
            self.calls += 1
            raise ProviderError("service unavailable")

    llm, _ = llm_for("deepseek", [])
    completions = BrokenCompletions()
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    llm._api_error_class = ProviderError
    with pytest.raises(RuntimeError, match="deepseek API.*service unavailable"):
        llm.generate("sys", "user", [], SCHEMA)
    assert completions.calls == 1
