from __future__ import annotations

import json

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
                f" Context selected {len(context.selected_memories)} memory item(s)."
            )
            if context.tool_evidence:
                suffix += f" Tool evidence count: {len(context.tool_evidence)}."

        if getattr(agent, "output_mode", "text") == "json_schema":
            schema = getattr(agent, "output_schema", None)
            if not isinstance(schema, dict):
                return AgentOutput(
                    type=OutputType.ERROR,
                    content="Structured output mode requires a valid JSON schema.",
                    confidence=Confidence(
                        level="low",
                        score=0.1,
                        basis=["runtime_config_error"],
                        uncertainties=["output_schema missing for json_schema mode"],
                        requires_human_check=True,
                    ),
                )
            obj = self._build_placeholder_from_schema(schema)
            if obj is None:
                return AgentOutput(
                    type=OutputType.ERROR,
                    content="Local runtime could not deterministically satisfy output schema.",
                    confidence=Confidence(
                        level="low",
                        score=0.1,
                        basis=["runtime_config_error"],
                        uncertainties=["unsupported_output_schema_shape"],
                        requires_human_check=True,
                    ),
                )
            return AgentOutput(
                type=OutputType.FINAL,
                content=json.dumps(obj, ensure_ascii=True, separators=(",", ":")),
                content_json=obj,
                confidence=Confidence(
                    level="medium",
                    score=0.55,
                    basis=["user_input", "local_runtime", "json_schema_mode"],
                    uncertainties=["This is a deterministic placeholder, not an LLM result."],
                    requires_human_check=True,
                ),
            )

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

    @classmethod
    def _build_placeholder_from_schema(cls, schema: dict) -> dict | list | str | int | float | bool | None:
        schema_type = schema.get("type")
        if schema_type == "object":
            props = schema.get("properties", {})
            if not isinstance(props, dict):
                return None
            required = schema.get("required", [])
            required_keys = [key for key in required if isinstance(key, str)]
            keys = required_keys or list(props.keys())
            obj: dict = {}
            for key in keys:
                prop_schema = props.get(key, {"type": "string"})
                value = cls._build_placeholder_from_schema(prop_schema if isinstance(prop_schema, dict) else {"type": "string"})
                if value is None and prop_schema is not None:
                    return None
                obj[key] = value
            return obj
        if schema_type == "array":
            items = schema.get("items", {"type": "string"})
            if not isinstance(items, dict):
                return []
            value = cls._build_placeholder_from_schema(items)
            if value is None:
                return []
            return [value]
        if schema_type == "string":
            return "placeholder"
        if schema_type == "integer":
            return 0
        if schema_type == "number":
            return 0.0
        if schema_type == "boolean":
            return False
        if isinstance(schema_type, list):
            for st in schema_type:
                value = cls._build_placeholder_from_schema({"type": st})
                if value is not None:
                    return value
        return None
