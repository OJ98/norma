from anthropic import Anthropic
from .model import LLM, LLMResponse, Message, ToolCall

class AnthropicLLM(LLM):
    def __init__(self, model:str, api_key: str | None = None, max_tokens: int = 4096):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, messages: list[Message], tools: list[dict]) -> LLMResponse:
        response = self.client.messages.create(model=self.model, max_tokens = self.max_tokens, messages=[{"role": m.role, "content": m.content} for m in messages], tools=tools)

        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_call":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        return LLMResponse(content=content, tool_calls=tool_calls)