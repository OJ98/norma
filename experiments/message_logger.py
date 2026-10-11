from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from norma.llm import LLM, LLMResponse, ToolCall


def new_log_path(experiment_name: str = "experiment", directory: str | Path = "experiments/logs") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    prefix = re.sub(r"[^a-z0-9]+", "_", experiment_name.lower()).strip("_") or "experiment"
    return Path(directory) / f"{prefix}_{timestamp}.log"


def new_structured_log_path(experiment_name: str = "experiment", directory: str | Path = "experiments/logs") -> Path:
    return new_log_path(experiment_name, directory).with_suffix(".jsonl")


def _json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if hasattr(value, "value"):
        return _json_value(value.value)
    if hasattr(value, "hex") and not isinstance(value, (str, bytes)):
        return str(value)
    return value


class StructuredEventLogger:
    """Append-only JSONL logger for reconstructing experiment trajectories."""

    def __init__(self, log_path: str | Path, run_id: str | None = None, base: dict[str, Any] | None = None):
        self.log_path = Path(log_path)
        self.run_id = run_id or str(uuid.uuid4())
        self.base = dict(base or {})
        self._sequence = 0

    def emit(self, event_type: str, **data: Any) -> dict[str, Any]:
        self._sequence += 1
        event = {
            "sequence": self._sequence,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            **_json_value(self.base),
            **_json_value(data),
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(event, sort_keys=True, default=str) + "\n")
        return event


class MessageLoggingLLM(LLM):
    """Record readable request and response transcripts for an experiment."""

    def __init__(
        self,
        llm: LLM,
        log_path: str | Path,
        event_logger: StructuredEventLogger | None = None,
        provider: str | None = None,
        model: str | None = None,
    ):
        self.llm = llm
        self.log_path = Path(log_path)
        self.event_logger = event_logger
        self.provider = provider
        self.model = model
        self.role = "unknown"
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
        started = time.perf_counter()
        self._write_request(call_number, system_prompt, user_prompt, tools, output_schema)
        if self.event_logger is not None:
            self.event_logger.emit(
                "MODEL_CALL_STARTED",
                call_id=f"llm-{call_number}",
                call_number=call_number,
                component=self.role,
                provider=self.provider,
                model=self.model,
                prompt={"system": system_prompt, "user": user_prompt},
                tool_definitions=tools,
                output_schema=output_schema,
            )

        try:
            response = self.llm.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                tools=tools,
                output_schema=output_schema,
            )
        except Exception as error:
            self._write_section(call_number, "ERROR", str(error))
            if self.event_logger is not None:
                self.event_logger.emit(
                    "MODEL_CALL_FAILED",
                    call_id=f"llm-{call_number}",
                    component=self.role,
                    error=str(error),
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            raise

        self._write_section(call_number, "RESPONSE", self._format_response(response))
        if self.event_logger is not None:
            self.event_logger.emit(
                "MODEL_CALL_COMPLETED",
                call_id=f"llm-{call_number}",
                call_number=call_number,
                component=self.role,
                provider=self.provider,
                model=self.model,
                response={
                    "content": response.content,
                    "structured_output": response.structured_output,
                    "tool_call_ids": [call.id for call in response.tool_calls],
                },
                tool_calls=response.tool_calls,
                usage=response.usage,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        return response

    def set_role(self, role: str) -> None:
        self.role = role

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
        if self.event_logger is not None:
            self.event_logger.emit(
                "TOOL_CALL_COMPLETED",
                call_id=tool_call.id,
                component=self.role,
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
                result=result,
            )
            if tool_call.name == "evaluate_action":
                self.event_logger.emit(
                    "NORM_EVALUATED",
                    phase="proposal",
                    tool_call_id=tool_call.id,
                    action=tool_call.arguments.get("actiondict"),
                    evaluation=result,
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
