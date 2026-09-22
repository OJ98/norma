from dataclasses import dataclass
from typing import Any
from abc import ABC, abstractmethod

@dataclass
class Message:
    role: str
    content: str

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]

# Define an abstract base class for LLMs that enforces the implementation of the generate method
class LLM(ABC):
    @abstractmethod
    def generate(self, messages: list[Message], tools: list[dict]) -> LLMResponse:
        pass