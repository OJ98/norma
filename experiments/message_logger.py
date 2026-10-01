from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from norma.llm import LLM, LLMResponse, ToolCall


def new_log_path(directory: str | Path = "experiments/logs") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    return Path(directory) / f"experiment_0_{timestamp}.log"


class MessageLoggingLLM(LLM):
    """Record readable request and response transcripts for an experiment."""

    def __init__(self, llm: LLM, log_path: str | Path):
        self.llm = llm
        self.log_path = Path(log_path)
        self._call_number = 0
        set_tool_result_logger = getattr(llm, "set_tool_result_logger", None)
        if set_tool_result_logger is not None:
            set_tool_result_logger(self._log_tool_result)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        output_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self._call_number += 1
        call_number = self._call_number
        self._write_request(call_number, system_prompt, user_prompt, tools, output_schema)

        try:
            response = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                output_schema=output_schema,
            )
        except Exception as error:
            self._write_section(call_number, "ERROR", str(error))
            raise

        self._write_section(call_number, "RESPONSE", self._format_response(response))
        return response

    def _write_request(
        self,
        call_number: int,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
        output_schema: dict[str, Any] | None,
    ) -> None:
        self._write_section(
            call_number,
            "REQUEST",
            "\n".join(
                [
                    "SYSTEM PROMPT\n" + system_prompt.strip(),
                    "USER PROMPT\n" + user_prompt.strip(),
                    "TOOLS\n" + self._format_value(tools),
                    "OUTPUT SCHEMA\n" + self._format_value(output_schema),
                ]
            ),
        )

    def _write_section(self, call_number: int, title: str, content: str) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n{'=' * 80}\n")
            log_file.write(f"CALL {call_number} | {title} | {timestamp}\n")
            log_file.write(f"{'=' * 80}\n")
            log_file.write(content.rstrip() + "\n")

    def _log_tool_result(self, tool_call: ToolCall, result: Any) -> None:
        self._write_section(
            self._call_number,
            "TOOL RESULT",
            "\n".join(
                [
                    f"TOOL NAME\n{tool_call.name}",
                    f"TOOL CALL ID\n{tool_call.id}",
                    "ARGUMENTS\n" + self._format_value(tool_call.arguments),
                    "RESULT\n" + self._format_value(result),
                ]
            ),
        )

    @staticmethod
    def _format_value(value: Any) -> str:
        return json.dumps(value, indent=2, sort_keys=True, default=str)

    @classmethod
    def _format_response(cls, response: LLMResponse) -> str:
        return "\n".join(
            [
                "CONTENT\n" + str(response.content),
                "TOOL CALLS\n" + cls._format_value(response.tool_calls),
                "STRUCTURED OUTPUT\n" + cls._format_value(response.structured_output),
            ]
        )
