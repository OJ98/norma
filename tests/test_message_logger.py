from pathlib import Path

from norma.llm import LLM, LLMResponse, ToolCall

from experiments.message_logger import MessageLoggingLLM


class FakeLLM(LLM):
    def generate(self, system_prompt, user_prompt, tools, output_schema=None):
        return LLMResponse(
            content="response",
            tool_calls=[],
            structured_output={"ok": True},
        )


class ToolLoggingLLM(FakeLLM):
    def set_tool_result_logger(self, logger):
        self.tool_result_logger = logger

    def generate(self, system_prompt, user_prompt, tools, output_schema=None):
        self.tool_result_logger(
            ToolCall("call-1", "evaluate_action", {"actiondict": {"type": "use"}}),
            {"evaluations": [{"status": "violated"}]},
        )
        return super().generate(system_prompt, user_prompt, tools, output_schema)


def test_message_logger_writes_readable_request_and_response(tmp_path: Path):
    log_path = tmp_path / "experiment.log"
    llm = MessageLoggingLLM(FakeLLM(), log_path)

    llm.generate(
        system_prompt="System instructions",
        user_prompt="Goal: use the GPU",
        tools=[],
        output_schema={"type": "object"},
    )

    transcript = log_path.read_text(encoding="utf-8")
    assert "SYSTEM PROMPT\nSystem instructions" in transcript
    assert "USER PROMPT\nGoal: use the GPU" in transcript
    assert "CONTENT\nresponse" in transcript
    assert '"ok": true' in transcript


def test_message_logger_writes_internal_tool_results(tmp_path: Path):
    log_path = tmp_path / "experiment.log"
    llm = MessageLoggingLLM(ToolLoggingLLM(), log_path)

    llm.generate("System", "Goal", [], None)

    transcript = log_path.read_text(encoding="utf-8")
    assert "CALL 1 | TOOL RESULT" in transcript
    assert "TOOL NAME\nevaluate_action" in transcript
    assert '"status": "violated"' in transcript