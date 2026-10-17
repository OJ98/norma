from types import SimpleNamespace

import pytest

from norma.llm.anthropic import AnthropicLLM


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"approved": true}')],
            stop_reason="end_turn",
        )


def test_anthropic_llm_uses_current_structured_output_format():
    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm.model = "test-model"
    llm.max_tokens = 128
    llm.client = SimpleNamespace(messages=FakeMessages())

    schema = {"type": "object", "properties": {"approved": {"type": "boolean"}}}
    response = llm.generate("system", "user", [], schema)

    assert llm.client.messages.kwargs["output_config"] == {
        "format": {
            "type": "json_schema",
            "schema": schema,
        }
    }
    assert response.structured_output == {"approved": True}


def test_anthropic_truncation_error_reports_effective_limit_and_usage():
    llm = AnthropicLLM.__new__(AnthropicLLM)
    llm.model = "test-model"
    llm.max_tokens = 8192
    llm.client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"approved":')],
                stop_reason="max_tokens",
                usage=SimpleNamespace(output_tokens=8192),
            )
        )
    )

    with pytest.raises(RuntimeError, match=r"model=test-model, max_tokens=8192, output_tokens=8192"):
        llm.generate("system", "user", [], {"type": "object"})
