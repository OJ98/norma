import os
from typing import Any, Callable

from .model import LLM, ToolCall


def configured_provider() -> tuple[str, str]:
    provider = os.getenv("NORMA_PROVIDER", "anthropic").strip().lower()
    defaults = {
        "anthropic": "claude-haiku-4-5-20251001",
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
    }
    if provider not in defaults:
        raise ValueError(f"Unsupported NORMA_PROVIDER {provider!r}; choose anthropic, openai, or deepseek.")
    return provider, os.getenv("NORMA_MODEL", defaults[provider])


def configured_max_tokens() -> int:
    raw_value = os.getenv("NORMA_MAX_TOKENS", "4096")
    try:
        max_tokens = int(raw_value)
    except ValueError as error:
        raise ValueError(f"NORMA_MAX_TOKENS must be a positive integer; got {raw_value!r}.") from error
    if max_tokens <= 0:
        raise ValueError(f"NORMA_MAX_TOKENS must be a positive integer; got {raw_value!r}.")
    return max_tokens


def create_configured_llm(
    tool_executor: Callable[[str, dict[str, Any]], Any] | None = None,
    tool_result_logger: Callable[[ToolCall, Any], None] | None = None,
) -> LLM:
    provider, model = configured_provider()
    max_tokens = configured_max_tokens()
    if provider == "anthropic":
        from .anthropic import AnthropicLLM
        return AnthropicLLM(model=model, max_tokens=max_tokens, tool_executor=tool_executor, tool_result_logger=tool_result_logger)
    from .openai_compatible import OpenAICompatibleLLM
    if provider == "deepseek":
        return OpenAICompatibleLLM(
            model=model, provider=provider, max_tokens=max_tokens, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            tool_executor=tool_executor, tool_result_logger=tool_result_logger,
        )
    return OpenAICompatibleLLM(model=model, provider=provider, max_tokens=max_tokens, tool_executor=tool_executor, tool_result_logger=tool_result_logger)
