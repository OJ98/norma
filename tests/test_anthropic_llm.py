from types import SimpleNamespace

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