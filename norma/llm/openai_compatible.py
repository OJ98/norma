"""OpenAI Chat Completions adapter for OpenAI and compatible providers."""

import json
import os
from typing import Any, Callable

from .model import LLM, LLMResponse, ToolCall


class OpenAICompatibleLLM(LLM):
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        provider: str = "openai",
        max_tokens: int = 4096,
        tool_executor: Callable[[str, dict[str, Any]], Any] | None = None,
        tool_result_logger: Callable[[ToolCall, Any], None] | None = None,
    ):
        key = api_key or os.getenv("OPENAI_API_KEY" if provider == "openai" else "DEEPSEEK_API_KEY")
        if not key:
            variable = "OPENAI_API_KEY" if provider == "openai" else "DEEPSEEK_API_KEY"
            raise RuntimeError(f"Missing API credentials: set {variable} for provider {provider}.")
        try:
            from openai import APIError, OpenAI
        except ImportError as error:
            raise RuntimeError("The OpenAI SDK is required for OpenAI and DeepSeek providers; install requirements.txt.") from error
        self._api_error_class = APIError
        self.client = OpenAI(api_key=key, base_url=base_url)
        self.model = model
        self.provider = provider
        self.max_tokens = max_tokens
        self.tool_executor = tool_executor
        self.tool_result_logger = tool_result_logger

    def set_tool_result_logger(self, logger: Callable[[ToolCall, Any], None]) -> None:
        self.tool_result_logger = logger

    def generate(self, system_prompt: str, user_prompt: str, tools: list[dict], output_schema: dict | None = None) -> LLMResponse:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": [self._format_tool(tool) for tool in tools] or None,
        }
        # Current OpenAI reasoning models (including GPT-5) require
        # max_completion_tokens. Keep max_tokens for compatible providers such
        # as DeepSeek, whose API uses the older parameter.
        kwargs["max_completion_tokens" if self.provider == "openai" else "max_tokens"] = self.max_tokens
        if output_schema:
            if self.provider == "openai":
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "norma_output", "strict": False, "schema": output_schema},
                }
            else:
                # DeepSeek supports JSON mode, not the OpenAI JSON Schema format.
                kwargs["response_format"] = {"type": "json_object"}

        all_tool_calls: list[ToolCall] = []
        response = None
        for _ in range(5):
            try:
                response = self.client.chat.completions.create(**kwargs)
            except self._api_error_class as error:
                raise RuntimeError(f"Error occurred while calling {self.provider} API: {error}") from error
            choice = response.choices[0]
            calls = self._get_tool_calls(getattr(choice.message, "tool_calls", None) or [])
            all_tool_calls.extend(calls)
            if not calls or self.tool_executor is None:
                break
            messages.append(choice.message.model_dump(exclude_none=True))
            for call in calls:
                try:
                    result = self.tool_executor(call.name, call.arguments)
                except Exception as error:
                    result = {"error": str(error)}
                if self.tool_result_logger is not None:
                    self.tool_result_logger(call, result)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": self._format_tool_result(result)})
            kwargs["messages"] = messages

        if response is None:
            raise RuntimeError(f"{self.provider} API returned no response.")
        choice = response.choices[0]
        content = getattr(choice.message, "content", None)
        structured_output = None
        if output_schema is not None:
            if getattr(choice, "finish_reason", None) == "length":
                raise RuntimeError(f"{self.provider} API response was truncated due to max token limit.")
            if content is None:
                raise RuntimeError(f"No text content returned from {self.provider} API, but output_schema was provided.")
            try:
                structured_output = json.loads(content)
            except (json.JSONDecodeError, TypeError) as error:
                raise RuntimeError(f"Failed to parse structured output as JSON: {error}") from error
            try:
                from jsonschema import ValidationError, validate
                validate(instance=structured_output, schema=output_schema)
            except ImportError as error:
                raise RuntimeError("The jsonschema package is required to validate structured model output.") from error
            except ValidationError as error:
                raise RuntimeError(f"Structured output does not match the requested schema: {error.message}") from error

        usage_obj = getattr(response, "usage", None)
        usage = None
        if usage_obj is not None:
            usage = {}
            if getattr(usage_obj, "prompt_tokens", None) is not None:
                usage["input_tokens"] = usage_obj.prompt_tokens
            if getattr(usage_obj, "completion_tokens", None) is not None:
                usage["output_tokens"] = usage_obj.completion_tokens
            if getattr(usage_obj, "total_tokens", None) is not None:
                usage["total_tokens"] = usage_obj.total_tokens
            if not usage:
                usage = None
        return LLMResponse(content=content, tool_calls=all_tool_calls, structured_output=structured_output, usage=usage)

    @staticmethod
    def _format_tool(tool: dict) -> dict:
        return {"type": "function", "function": {
            "name": tool["name"], "description": tool.get("description", ""),
            "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
        }}

    @staticmethod
    def _get_tool_calls(calls: list[Any]) -> list[ToolCall]:
        parsed = []
        for call in calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError) as error:
                raise RuntimeError(f"Failed to parse {call.function.name} tool arguments as JSON: {error}") from error
            if not isinstance(arguments, dict):
                raise RuntimeError(f"Tool arguments for {call.function.name} must be a JSON object.")
            parsed.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        return parsed

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        if hasattr(result, "model_dump"):
            result = result.model_dump(exclude_none=True)
        return json.dumps(result, default=str)
