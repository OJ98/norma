from anthropic import Anthropic, APIError
from .model import LLM, LLMResponse, ToolCall
import json
from typing import Any, Callable

class AnthropicLLM(LLM):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        max_tokens: int = 4096,
        tool_executor: Callable[[str, dict[str, Any]], Any] | None = None,
        tool_result_logger: Callable[[ToolCall, Any], None] | None = None,
    ):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.tool_executor = tool_executor
        self.tool_result_logger = tool_result_logger

    def set_tool_result_logger(self, logger: Callable[[ToolCall, Any], None]) -> None:
        self.tool_result_logger = logger

    def generate(self, system_prompt:str, user_prompt: str, tools: list[dict], output_schema: dict | None = None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "tools": tools,
        }
        if output_schema:
            kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": output_schema,
                }
            }

        messages = list(kwargs["messages"])
        all_tool_calls = []
        response = None

        for _ in range(5):
            kwargs["messages"] = messages
            try:
                response = self.client.messages.create(**kwargs)
            except APIError as e:
                print(f"Error occurred while calling Anthropic API: {e}")
                return LLMResponse(content=None, tool_calls=[], structured_output=None)

            tool_calls = self._get_tool_calls(response.content)
            all_tool_calls.extend(tool_calls)
            if not tool_calls or self.tool_executor is None:
                break

            messages.append(self._serialize_assistant_message(response))
            tool_results = []
            for tool_call in tool_calls:
                try:
                    result = self.tool_executor(tool_call.name, tool_call.arguments)
                except Exception as error:
                    result = {"error": str(error)}
                if self.tool_result_logger is not None:
                    self.tool_result_logger(tool_call, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": self._format_tool_result(result),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        if response is None:
            raise RuntimeError("Anthropic API returned no response.")

        content = None
        block_types = []

        for block in response.content:
            block_type = getattr(block, "type", None)
            block_types.append(block_type)
            text = getattr(block, "text", None)
            if text is not None:
                content = text

        structured_output = None
        
        # Parse output into the provided output schema
        if output_schema is not None:
            if response.stop_reason == "refusal":
                raise RuntimeError("Anthropic refused to provide structured output.")
            if response.stop_reason == "max_tokens":
                raise RuntimeError("Warning: Anthropic API response was truncated due to max token limit. Structured output may be incomplete.")
            if content is None:
                raise RuntimeError(
                    "No text content returned from Anthropic API, but output_schema was provided. "
                    f"Response block types: {block_types}"
                )
            try:
                structured_output = json.loads(content)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse structured output as JSON: {e}")

        usage = getattr(response, "usage", None)
        if usage is not None:
            usage = {
                key: getattr(usage, key)
                for key in ("input_tokens", "output_tokens")
                if hasattr(usage, key)
            }
        return LLMResponse(
            content=content,
            tool_calls=all_tool_calls,
            structured_output=structured_output,
            usage=usage or None,
        )

    @staticmethod
    def _get_tool_calls(blocks: list[Any]) -> list[ToolCall]:
        calls = []
        for block in blocks:
            if getattr(block, "type", None) in ("tool_call", "tool_use"):
                calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=getattr(block, "input", {}),
                    )
                )
        return calls

    @staticmethod
    def _serialize_assistant_message(response: Any) -> dict[str, Any]:
        content = response.model_dump(exclude_none=True)["content"]
        return {"role": "assistant", "content": content}

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        if hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)
        return json.dumps(result, default=str)