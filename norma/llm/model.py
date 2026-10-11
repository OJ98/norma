from dataclasses import dataclass
from typing import Any
from abc import ABC, abstractmethod


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    structured_output: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None

# Define an abstract base class for LLMs that enforces the implementation of the generate method
class LLM(ABC):
    @abstractmethod
    def generate(self, system_prompt:str, user_prompt: str, tools: list[dict[str, Any]], output_schema: dict[str, Any] | None=None) -> LLMResponse:
        pass