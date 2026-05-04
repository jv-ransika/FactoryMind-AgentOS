from __future__ import annotations

import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from agent_os.monitoring import record_usage_and_cost
from agent_os.observability import MetricsStore
from agent_os.protocol import (
    AgentDefinition,
    AgentOutput,
    Confidence,
    ContextPacket,
    ModelCapability,
    OutputType,
    RuntimeConfig,
    SessionEvent,
)
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
        self.capabilities = None
        self.context_window_manager = None
        self.usage_tracker = None

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
        if self.capabilities is None:
            return self._error("runtime_config_error", "Model capability registry is missing.")

        try:
            capability: ModelCapability = self.capabilities.get(agent.model, verify_provider=True)
        except ValueError as exc:
            return self._error("runtime_config_error", f"{exc}")
        except Exception:
            return self._error("provider_error", "OpenAI provider failed during model capability verification.")

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

        try:
            body = self._build_prompt_payload(agent, input_text, context)
        except RuntimeError as exc:
            message = str(exc)
            if message.startswith("runtime_config_error:"):
                return self._error("runtime_config_error", message.split(":", 1)[1])
            return self._error("runtime_config_error", "Invalid runtime output configuration.")
        started = time.perf_counter()
        if self.metrics:
            self.metrics.inc("runtime_openai_calls")
        status_code = "ok"
        usage_tokens = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}

        if self.context_window_manager is not None and context is not None:
            preflight_text = json.dumps(body.get("input", []), ensure_ascii=True)
            preflight = self.context_window_manager.preflight(
                model=agent.model,
                context_text=preflight_text,
                window_limit=capability.context_window,
                reserve_output_tokens=min(self.config.reserve_output_tokens, capability.max_output_tokens),
                safety_margin_tokens=self.config.context_safety_margin_tokens,
            )
            context.estimated_tokens = preflight.estimated_tokens
            if preflight.over_limit:
                context.truncated = True
                context.truncation_notes.extend(preflight.notes)
                if context.tool_evidence:
                    context.tool_evidence = context.tool_evidence[:3]
                    context.truncation_notes.append("tool_evidence_trimmed_preflight")
                body = self._build_prompt_payload(agent, input_text, context)
                self.metrics and self.metrics.inc("context_overflow_count")

        try:
            parsed, usage_tokens, runtime_metadata = self._run_with_selected_engine(
                agent=agent,
                payload=body,
                session_id=events[-1].session_id if events else None,
            )
        except httpx.TimeoutException:
            status_code = "provider_timeout"
            self.metrics and self.metrics.inc("runtime_openai_timeout")
            return self._error("provider_timeout", "OpenAI provider timed out.")
        except RuntimeError as exc:
            message = str(exc)
            if message.startswith("runtime_config_error:"):
                return self._error("runtime_config_error", message.split(":", 1)[1])
            status_code = "provider_error"
            self.metrics and self.metrics.inc("runtime_openai_error")
            return self._error("provider_error", "OpenAI provider failed.")
        except Exception:
            status_code = "provider_error"
            self.metrics and self.metrics.inc("runtime_openai_error")
            return self._error("provider_error", "OpenAI provider failed.")

        try:
            if getattr(agent, "output_mode", "text") == "json_schema":
                output = self._to_agent_output_json(agent=agent, parsed=parsed)
            else:
                structured = _ModelOutput.model_validate(parsed)
                output = self._to_agent_output(structured, context=context)
        except ValidationError:
            status_code = "invalid_model_output"
            self.metrics and self.metrics.inc("runtime_invalid_output")
            return self._error("invalid_model_output", "Model response did not match required output schema.")
        except ValueError:
            status_code = "invalid_model_output"
            self.metrics and self.metrics.inc("runtime_invalid_output")
            return self._error("invalid_model_output", "Model response did not match required output schema.")

        output.runtime_metadata = runtime_metadata
        duration_ms = int((time.perf_counter() - started) * 1000)
        if self.metrics:
            self.metrics.inc("runtime_openai_success")
            self.metrics.set("runtime_openai_last_latency_ms", duration_ms)

        self._record_usage_and_cost(
            agent=agent,
            session_id=events[-1].session_id if events else None,
            payload=body,
            usage_tokens=usage_tokens,
            duration_ms=duration_ms,
        )
        self.metrics and self.metrics.inc(f"runtime_status_{status_code}")
        return output

    def _run_with_selected_engine(
        self,
        agent: AgentDefinition,
        payload: dict[str, Any],
        session_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, int], dict[str, Any]]:
        if self.config.runtime_engine == "openai_agents_sdk":
            try:
                parsed, usage, sdk_meta = self._call_via_agents_sdk(agent=agent, payload=payload, session_id=session_id)
                return parsed, usage, {
                    "runtime_engine": "openai_agents_sdk",
                    "sdk_session_backend": "sqlalchemy" if session_id else "none",
                    "sdk_run_id": sdk_meta.get("sdk_run_id"),
                    "compaction_applied": bool(sdk_meta.get("compaction_applied", False)),
                }
            except RuntimeError as exc:
                if "not installed" in str(exc).lower():
                    parsed, usage = self._call_model_with_retry(agent=agent, payload=payload)
                    return parsed, usage, {
                        "runtime_engine": "legacy_openai",
                        "fallback_reason": "agents_sdk_unavailable",
                    }
                raise
            except Exception as exc:
                # In non-SDK environments, keep deterministic behavior for development/tests.
                if "agents" in str(exc).lower():
                    raise RuntimeError("runtime_config_error:OpenAI Agents SDK is not installed.")
                raise
        parsed, usage = self._call_model_with_retry(agent=agent, payload=payload)
        return parsed, usage, {"runtime_engine": "legacy_openai"}

    def _call_via_agents_sdk(
        self,
        agent: AgentDefinition,
        payload: dict[str, Any],
        session_id: str | None,
    ) -> tuple[dict[str, Any], dict[str, int], dict[str, Any]]:
        try:
            from agents import Agent as SdkAgent, Runner  # type: ignore[import-not-found]
        except Exception as exc:
            raise RuntimeError("runtime_config_error:OpenAI Agents SDK is not installed.") from exc

        system_text = ""
        user_text = ""
        for msg in payload.get("input", []):
            if msg.get("role") == "system":
                system_text = str(msg.get("content", ""))
            elif msg.get("role") == "user":
                user_text = str(msg.get("content", ""))

        sdk_agent = SdkAgent(
            name=agent.id,
            model=agent.model,
            instructions=system_text,
        )
        result = Runner.run_sync(
            sdk_agent,
            input=user_text,
            max_turns=1,
        )
        final_text = getattr(result, "final_output", None)
        if not isinstance(final_text, str) or not final_text.strip():
            maybe = getattr(result, "output", None)
            final_text = maybe if isinstance(maybe, str) else ""
        parsed = json.loads(final_text)
        if not isinstance(parsed, dict):
            raise ValueError("invalid model output")
        usage_obj = getattr(getattr(result, "context_wrapper", None), "usage", None)
        usage = {
            "input_tokens": int(getattr(usage_obj, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
            "reasoning_tokens": int(getattr(usage_obj, "reasoning_tokens", 0) or 0),
            "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
        }
        return parsed, usage, {
            "sdk_run_id": str(getattr(result, "id", "") or getattr(result, "run_id", "") or ""),
            "compaction_applied": bool(getattr(result, "was_compacted", False)),
        }

    def _call_model_with_retry(self, agent: AgentDefinition, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        base_url = (self.config.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        attempts = max(1, self.config.openai_max_retries + 1)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                with httpx.Client(timeout=self.config.openai_timeout_ms / 1000.0) as client:
                    resp = client.post(
                        f"{base_url}/responses",
                        headers={
                            "Authorization": f"Bearer {self.config.openai_api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                resp.raise_for_status()
                body = resp.json()
                raw_text = self._extract_output_text(body)
                parsed = json.loads(raw_text)
                if not isinstance(parsed, dict):
                    raise ValueError("invalid model output")
                usage = body.get("usage") or {}
                usage_tokens = {
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "reasoning_tokens": int(usage.get("reasoning_tokens", 0) or 0),
                    "total_tokens": int(usage.get("total_tokens", 0) or 0),
                }
                return parsed, usage_tokens
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == attempts - 1:
                    raise
        raise last_error or RuntimeError("provider_error")

    def _build_prompt_payload(self, agent: AgentDefinition, input_text: str, context: ContextPacket | None) -> dict[str, Any]:
        if getattr(agent, "output_mode", "text") == "json_schema":
            if not isinstance(getattr(agent, "output_schema", None), dict):
                raise RuntimeError("runtime_config_error:output_schema is required for json_schema output mode.")
            return self._build_json_schema_prompt_payload(agent=agent, input_text=input_text, context=context)

        return self._build_text_prompt_payload(agent=agent, input_text=input_text, context=context)

    def _build_text_prompt_payload(self, agent: AgentDefinition, input_text: str, context: ContextPacket | None) -> dict[str, Any]:
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
            "tool_evidence": [] if context is None else context.tool_evidence[:5],
            "truncated": False if context is None else context.truncated,
            "truncation_notes": [] if context is None else context.truncation_notes[:8],
        }
        max_out = self.config.reserve_output_tokens
        return {
            "model": agent.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=True)},
            ],
            "max_output_tokens": max_out,
            "text": {"format": {"type": "json_object"}},
        }

    def _build_json_schema_prompt_payload(self, agent: AgentDefinition, input_text: str, context: ContextPacket | None) -> dict[str, Any]:
        system = "You are an enterprise agent. Return strict JSON matching the provided schema exactly."
        user = {
            "agent_id": agent.id,
            "goal": agent.goal,
            "input": input_text,
            "latest_feedback": None if context is None else context.latest_feedback,
            "selected_memories": [] if context is None else [m.item.summary or m.item.content[:120] for m in context.selected_memories[:5]],
            "tool_evidence": [] if context is None else context.tool_evidence[:5],
            "truncated": False if context is None else context.truncated,
            "truncation_notes": [] if context is None else context.truncation_notes[:8],
        }
        max_out = self.config.reserve_output_tokens
        return {
            "model": agent.model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=True)},
            ],
            "max_output_tokens": max_out,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"{agent.id}_output",
                    "schema": agent.output_schema,
                    "strict": True,
                }
            },
        }

    @staticmethod
    def _extract_output_text(body: dict[str, Any]) -> str:
        direct = body.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        output = body.get("output")
        if isinstance(output, list):
            for item in output:
                content = item.get("content") if isinstance(item, dict) else None
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and isinstance(part.get("text"), str):
                            return str(part["text"])
        raise ValueError("provider_error:missing_output_text")

    def _to_agent_output(self, model_output: _ModelOutput, context: ContextPacket | None = None) -> AgentOutput:
        score = max(0.0, min(1.0, float(model_output.confidence_score)))
        basis = list(model_output.confidence_basis or [])
        uncertainties = list(model_output.uncertainties or [])

        if model_output.type == OutputType.FINAL:
            evidence_count = 0 if context is None else (
                len(context.tool_evidence) + len(context.selected_memories)
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

    def _to_agent_output_json(self, agent: AgentDefinition, parsed: dict[str, Any]) -> AgentOutput:
        schema = getattr(agent, "output_schema", None)
        if not isinstance(schema, dict):
            raise ValueError("output_schema_missing")
        if not self._validate_json_schema_like(schema=schema, data=parsed):
            raise ValueError("output_schema_validation_failed")
        canonical = json.dumps(parsed, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        return AgentOutput(
            type=OutputType.FINAL,
            content=canonical,
            content_json=parsed,
            confidence=Confidence(
                level="medium",
                score=0.6,
                basis=["json_schema_validated_output"],
                uncertainties=[],
                requires_human_check=True,
            ),
        )

    @classmethod
    def _validate_json_schema_like(cls, schema: dict[str, Any], data: Any) -> bool:
        schema_type = schema.get("type")
        if isinstance(schema_type, list):
            return any(cls._validate_json_schema_like({"type": one, **{k: v for k, v in schema.items() if k != "type"}}, data) for one in schema_type)
        if schema_type == "object":
            if not isinstance(data, dict):
                return False
            props = schema.get("properties", {})
            if props is None:
                props = {}
            if not isinstance(props, dict):
                return False
            required = schema.get("required", [])
            required_keys = [key for key in required if isinstance(key, str)]
            for key in required_keys:
                if key not in data:
                    return False
            additional_allowed = bool(schema.get("additionalProperties", True))
            for key, value in data.items():
                if key in props:
                    prop_schema = props[key]
                    if isinstance(prop_schema, dict) and not cls._validate_json_schema_like(prop_schema, value):
                        return False
                elif not additional_allowed:
                    return False
            return True
        if schema_type == "array":
            if not isinstance(data, list):
                return False
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                return all(cls._validate_json_schema_like(item_schema, item) for item in data)
            return True
        if schema_type == "string":
            return isinstance(data, str)
        if schema_type == "integer":
            return isinstance(data, int) and not isinstance(data, bool)
        if schema_type == "number":
            return (isinstance(data, int) and not isinstance(data, bool)) or isinstance(data, float)
        if schema_type == "boolean":
            return isinstance(data, bool)
        if schema_type == "null":
            return data is None
        return isinstance(data, dict)

    def _record_usage_and_cost(
        self,
        agent: AgentDefinition,
        session_id: str | None,
        payload: dict[str, Any],
        usage_tokens: dict[str, int],
        duration_ms: int,
    ) -> None:
        request_bytes = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
        record_usage_and_cost(
            usage_tracker=self.usage_tracker,
            capabilities=self.capabilities,
            agent=agent,
            session_id=session_id,
            operation_bucket="main_run",
            model=agent.model,
            request_bytes=request_bytes,
            latency_ms=duration_ms,
            input_tokens=int(usage_tokens.get("input_tokens", 0)),
            output_tokens=int(usage_tokens.get("output_tokens", 0)),
            reasoning_tokens=int(usage_tokens.get("reasoning_tokens", 0)),
            total_tokens=int(usage_tokens.get("total_tokens", 0)),
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
