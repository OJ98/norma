from anthropic import Anthropic, APIError
from .model import LLM, LLMResponse, ToolCall
import json

class AnthropicLLM(LLM):
    def __init__(self, model:str, api_key: str | None = None, max_tokens: int = 4096):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, system_prompt:str, user_prompt: str, tools: list[dict], output_schema: dict | None = None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": tools,
        }
        if output_schema:
            kwargs["output_config"] =  {
                "type": "json_schema",
                "json_schema": output_schema
            }

        try:
            response = self.client.messages.create(**kwargs)
        except APIError as e:
            print(f"Error occurred while calling Anthropic API: {e}")
            return LLMResponse(content=None, tool_calls=[], structured_output=None)

        content = None
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_call":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))

        structured_output = None
        
        # Parse output into the provided output schema
        if output_schema is not None:
            if response.stop_reason == "refusal":
                raise RuntimeError("Anthropic refused to provide structured output.")
            if response.stop_reason == "max_tokens":
                raise RuntimeError("Warning: Anthropic API response was truncated due to max token limit. Structured output may be incomplete.")
            if content is None:
                raise RuntimeError("No content returned from Anthropic API, but output_schema was provided.")
            try:
                structured_output = json.loads(content)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse structured output as JSON: {e}")

        return LLMResponse(content=content, tool_calls=tool_calls, structured_output=structured_output)        