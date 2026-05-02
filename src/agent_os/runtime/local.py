from __future__ import annotations

from agent_os.protocol import AgentDefinition, AgentOutput, Confidence, ContextPacket, OutputType, SessionEvent
from agent_os.runtime.base import AgentRuntimeAdapter


class LocalRuntimeAdapter(AgentRuntimeAdapter):
    """Deterministic runtime for Iteration 1 protocol validation."""

    def run(
        self,
        agent: AgentDefinition,
        events: list[SessionEvent],
        input_text: str,
        context: ContextPacket | None = None,
    ) -> AgentOutput:
        if not input_text.strip():
            return AgentOutput(
                type=OutputType.QUESTION,
                content="What should this agent work on?",
                confidence=Confidence(
                    level="low",
                    score=0.2,
                    basis=["missing_input"],
                    uncertainties=["No task input was provided."],
                    requires_human_check=True,
                ),
            )

        feedback_count = sum(1 for event in events if event.type == "feedback")
        suffix = ""
        if feedback_count:
            suffix = f" I considered {feedback_count} feedback message(s) in this session."

        if context is not None:
            suffix += (
                f" Context selected {len(context.selected_memories)} memory item(s)"
                f" and {len(context.selected_skills)} skill(s)."
            )
            if context.tool_evidence:
                suffix += f" Tool evidence count: {len(context.tool_evidence)}."

        content = f"[LocalRuntime] {agent.id} handled: {input_text.rstrip('.')}."
        if suffix:
            content = f"{content}{suffix}"

        return AgentOutput(
            type=OutputType.FINAL,
            content=content,
            confidence=Confidence(
                level="medium",
                score=0.55,
                basis=["user_input", "local_runtime"],
                uncertainties=["This is a deterministic placeholder, not an LLM result."],
                requires_human_check=True,
            ),
        )
