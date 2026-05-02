from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from agent_os.observability import MetricsStore
from agent_os.protocol import AgentDefinition, AgentOutput, Confidence, ContextPacket, OutputType, RuntimeConfig, SessionEvent
from agent_os.runtime.base import AgentRuntimeAdapter


class _ModelOutput(BaseModel):
    type: OutputType
    content: str
    confidence_score: float = 0.5
    confidence_basis: list[str] = []
    uncertainties: list[str] = []


class OpenAIRuntimeAdapter(AgentRuntimeAdapter):
    def __init__(self, config: RuntimeConfig, metrics: MetricsStore | None = None) -> None:
        self.config = config
        self.metrics = metrics
        self.config_loader = None

    def run(
        self,
        agent: AgentDefinition,
        events: list[SessionEvent],
        input_text: str,
        context: ContextPacket | None = None,
    ) -> AgentOutput:
        if callable(self.config_loader):
            self.config = self.config_loader()
        if not self.config.openai_api_key:
            return self._error("runtime_config_error", "OpenAI API key is missing.")
        if not agent.model.strip():
            return self._error("runtime_config_error", "Agent model is missing.")
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

        started = time.perf_counter()
        if self.metrics:
            self.metrics.inc("runtime_openai_calls")
        try:
            payload = self._call_model(agent, input_text, context)
        except httpx.TimeoutException:
            if self.metrics:
                self.metrics.inc("runtime_openai_timeout")
            return self._error("provider_timeout", "OpenAI provider timed out.")
        except Exception:
            if self.metrics:
                self.metrics.inc("runtime_openai_error")
            return self._error("provider_error", "OpenAI provider failed.")

        try:
            structured = _ModelOutput.model_validate(payload)
        except ValidationError:
            if self.metrics:
                self.metrics.inc("runtime_invalid_output")
            return self._error("invalid_model_output", "Model response did not match required output schema.")

        output = self._to_agent_output(structured, context=context)
        if self.metrics:
            self.metrics.inc("runtime_openai_success")
            self.metrics.set("runtime_openai_last_latency_ms", int((time.perf_counter() - started) * 1000))
        return output

    def _call_model(self, agent: AgentDefinition, input_text: str, context: ContextPacket | None) -> dict[str, Any]:
        system = (
            "You are an enterprise agent. Return strict JSON with keys: "
            "type(question|final|error), content, confidence_score(0..1), confidence_basis(array), uncertainties(array)."
        )
        user = {
            "agent_id": agent.id,
            "goal": agent.goal,
            "input": input_text,
            "latest_feedback": None if context is None else context.latest_feedback,
            "selected_memories": [] if context is None else [m.item.summary or m.item.content[:120] for m in context.selected_memories[:5]],
            "selected_skills": [] if context is None else [s.skill.name for s in context.selected_skills[:5]],
            "tool_evidence": [] if context is None else context.tool_evidence[:5],
        }
        base_url = self.config.openai_base_url or "https://api.openai.com/v1"
        with httpx.Client(timeout=self.config.openai_timeout_ms / 1000.0) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": agent.model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps(user, ensure_ascii=True)},
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
        resp.raise_for_status()
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("invalid model output")
        return parsed

    def _to_agent_output(self, model_output: _ModelOutput, context: ContextPacket | None = None) -> AgentOutput:
        score = max(0.0, min(1.0, float(model_output.confidence_score)))
        basis = list(model_output.confidence_basis or [])
        uncertainties = list(model_output.uncertainties or [])

        if model_output.type == OutputType.FINAL:
            evidence_count = 0 if context is None else (
                len(context.tool_evidence) + len(context.selected_memories) + len(context.selected_skills)
            )
            if evidence_count < 2:
                score = min(score, 0.45)
                basis.append("weak_evidence_soft_gate")
                uncertainties.append("Final answer has weak supporting evidence in current context.")

        level = "low" if score < 0.4 else "medium" if score < 0.75 else "high"
        return AgentOutput(
            type=model_output.type,
            content=model_output.content,
            confidence=Confidence(
                level=level,
                score=score,
                basis=sorted(set(basis)),
                uncertainties=sorted(set(uncertainties)),
                requires_human_check=(score < 0.8),
            ),
        )

    @staticmethod
    def _error(code: str, message: str) -> AgentOutput:
        return AgentOutput(
            type=OutputType.ERROR,
            content=message,
            confidence=Confidence(
                level="low",
                score=0.1,
                basis=[code],
                uncertainties=[message],
                requires_human_check=True,
            ),
        )
