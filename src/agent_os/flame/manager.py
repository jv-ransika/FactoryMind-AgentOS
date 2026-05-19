from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from agent_os.capabilities import ModelCapabilityRegistry
from agent_os.flame.memory import FlameMemorySystem
from agent_os.monitoring import UsageTracker, record_usage_and_cost
from agent_os.observability import MetricsStore
from agent_os.protocol import (
    EventType,
    ExtractedItem,
    ExtractedType,
    FlamePoolState,
    FlameRunState,
    FlameStatus,
    MemoryType,
    PoolItem,
    ReflectionBatchRun,
    ReflectionItem,
    SessionRecord,
)
from agent_os.storage import DomainStore

FLAME_EXTRACTION_PROMPT_VERSION = "v0.1"
FLAME_TEMP_CONTENT_MAX_CHARS = 320
FLAME_REFLECTION_CONTENT_MAX_CHARS = 280
FLAME_EXTRACTION_SYSTEM_PROMPT = """You are a behavioral signal extraction agent. Your job is to analyze completed agent-human sessions and extract high-level behavioral learning signals from them.

You will receive a structured JSON payload. Based on the `mode` field, you operate in one of two modes:

---

MODE: "experience"
The session had no human feedback. The human accepted the output without corrections.

Your task:
- Extract what kind of task was performed
- Extract what approach the agent took
- Note the outcome was accepted without correction
- This is low learning signal - keep it brief and factual

---

MODE: "learning_point"
The session had human feedback. This is your primary signal.

Your task:
- Analyze every human_feedback entry in the exchange_log carefully
- Extract the behavioral pattern, preference, or correction the feedback implies
- Assign a human_feedback_weight between 0.0 and 1.0:
    - 1.0 = direct, explicit correction or instruction ("don't do X", "always do Y")
    - 0.7-0.9 = clear preference expressed ("I'd prefer...", "next time...")
    - 0.4-0.6 = implicit preference inferred from rephrasing or redirection
    - 0.1-0.3 = very subtle or ambiguous signal
- Include the exact feedback snippet(s) that led to each extracted item

---

EXTRACTION RULES - apply to both modes:

1. Extract PATTERNS and BEHAVIORS only. Never extract task content, data, or domain-specific details.
2. Your output must generalize. Ask yourself: "Would this insight help the agent in a different session on a different topic?" If no, do not include it.
3. Be specific, not vague. "User prefers concise answers" is good. "User likes good responses" is not.
4. One insight per item. Do not bundle multiple patterns into one content string.
5. If the exchange_log is empty or human_feedback fields are all null/empty, treat as mode "experience" regardless of the mode field.
6. Keep each `content` field at or under 320 characters.

---

GOOD extraction examples:
- "User corrects passive voice - always use active, direct language"
- "User expects error handling in code without being asked"
- "User prefers bullet points over paragraphs for summaries"
- "When user redirects mid-task, they want acknowledgment before the agent continues"

BAD extraction examples (do not do these):
- "User asked about Python Flask routing and wanted JSON response" <- task content
- "User was working on a CSV file with Q3 sales data" <- data content
- "Agent gave a good answer and user accepted it" <- not a behavioral pattern
- "User seems to prefer better answers" <- too vague

---

OUTPUT FORMAT:

Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown fences.

{
  "session_id": "<copy from input>",
  "mode": "<copy from input>",
  "items": [
    {
      "type": "experience" | "learning_point",
      "content": "<extracted behavioral insight>",
      "human_feedback_weight": <0.0-1.0>,
      "source_feedback_snippets": ["<exact quote from human_feedback>", "..."]
    }
  ]
}

For mode "experience": human_feedback_weight should be 0.0 and source_feedback_snippets should be [].
For mode "learning_point": there must be at least one item with human_feedback_weight > 0.0.
If nothing meaningful can be extracted, return items as an empty array []."""
FLAME_REFLECTION_PROMPT_VERSION = "v0.1"
FLAME_REFLECTION_SYSTEM_PROMPT = """You synthesize durable behavioral reflections from learning signals extracted from agent-human sessions.

You will receive a batch of extracted items from a temporary memory pool. Each item is either an "experience" (no human feedback was present) or a "learning_point" (derived from human feedback).

Your job is to look across all items and produce a small set of high-level behavioral reflections - durable insights that would genuinely help an agent perform better in future sessions.

---

WHEN TO REFLECT:

Reflect when the items contain:
- One or more learning_point items (human feedback was present)
- A clear behavioral pattern that repeats or is strongly signaled
- A preference, correction, or guideline that generalizes beyond the specific session

Do NOT reflect when the items contain:
- Only "experience" type items with human_feedback_weight of 0.0 or near 0.0
- Vague or ambiguous signals with no clear behavioral implication
- Only task-specific observations that do not generalize

If there is nothing meaningful to reflect on, return an empty reflections array. This is valid and expected - do not force a reflection where none is warranted.

---

REFLECTION RULES:

1. Each reflection must be a durable behavioral insight - something that holds true across sessions and topics.
2. Prioritize items with high human_feedback_weight. These are the strongest signals.
3. Do not include task content, data details, or domain-specific information in any reflection.
4. One clear idea per reflection. Do not bundle multiple insights together.
5. Keep each reflection `content` field at or under 280 characters.
6. Confidence score guidelines:
   - 0.9-1.0 -> backed by explicit, direct human correction or instruction
   - 0.7-0.8 -> backed by clear human preference expressed across one or more items
   - 0.5-0.6 -> inferred from implicit or indirect feedback signals
   - 0.2-0.4 -> weakly supported; pattern is possible but not clearly established
   - Set human_feedback_weighted to true if any contributing item has human_feedback_weight > 0.3

---

GOOD reflection examples:
- "Always use active voice; user consistently corrects passive constructions"
- "Include error handling in all code outputs without waiting to be asked"
- "When summarizing, use bullet points rather than prose paragraphs"
- "Acknowledge mid-task redirections explicitly before continuing"

BAD reflection examples (do not produce these):
- "User worked on a Flask API project" <- task content
- "Agent performed well in this session" <- not a behavioral reflection
- "User seems to prefer good responses" <- too vague to be actionable
- "Session involved CSV data processing" <- data content

---

OUTPUT FORMAT:

Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown fences.

{
  "reflections": [
    {
      "content": "<durable behavioral insight>",
      "confidence": <0.0-1.0>,
      "human_feedback_weighted": <true|false>
    }
  ]
}

If there is nothing meaningful to reflect on, return:
{
  "reflections": []
}"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FlameManager:
    def __init__(
        self,
        store: DomainStore,
        memory: FlameMemorySystem,
        runtime: Any | None = None,
        metrics: MetricsStore | None = None,
        usage_tracker: UsageTracker | None = None,
        capabilities: ModelCapabilityRegistry | None = None,
        pool_size_trigger: int = 12,
        time_trigger_hours: int = 24,
    ) -> None:
        self.store = store
        self.memory = memory
        self.runtime = runtime
        self.metrics = metrics
        self.usage_tracker = usage_tracker
        self.capabilities = capabilities
        self.pool_size_trigger = pool_size_trigger
        self.time_trigger_hours = time_trigger_hours

    def ingest_accepted_session(self, agent_id: str, session_id: str) -> dict[str, Any]:
        agent = self.store.load_agent(agent_id)
        session_record = self._build_session_record(agent_id=agent_id, session_id=session_id)
        extracted_items = self._extract_features(record=session_record)
        written = 0
        for item in extracted_items:
            content = self._cap_text(item.content, max_chars=FLAME_TEMP_CONTENT_MAX_CHARS, metric_name="flame_temp_content_truncated")
            pool = PoolItem(
                agent_id=agent_id,
                tenant_id=agent.tenant_id,
                session_id=item.session_id,
                extracted_type=item.type,
                content=content,
                human_feedback_weight=item.human_feedback_weight,
                source_feedback_snippets=item.source_feedback_snippets,
                embedding=self._embed(content),
                state=FlamePoolState.PENDING,
            )
            self.store.save_flame_pool_item(pool)
            written += 1
        self.metrics and self.metrics.inc("flame_pool_writes")
        triggered, reason = self._should_trigger(agent_id=agent_id, force=False)
        runs: list[ReflectionBatchRun] = []
        if triggered:
            runs = self.trigger(agent_id=agent_id, force=False)
        return {
            "session_id": session_id,
            "agent_id": agent_id,
            "pool_items_written": written,
            "triggered": triggered,
            "trigger_reason": reason,
            "run_ids": [run.run_id for run in runs],
        }

    def trigger(self, agent_id: str | None = None, force: bool = False) -> list[ReflectionBatchRun]:
        if agent_id:
            agent_ids = [agent_id]
        else:
            agent_ids = [agent.id for agent in self.store.list_agents() if getattr(agent, "agent_tier", "").value == "self_learning_agent"]
        runs: list[ReflectionBatchRun] = []
        for aid in agent_ids:
            triggered, reason = self._should_trigger(agent_id=aid, force=force)
            if not triggered:
                continue
            run = self._run_reflection(agent_id=aid, trigger_reason=reason)
            runs.append(run)
        return runs

    def list_pool(self, agent_id: str, state: FlamePoolState | None = None) -> list[PoolItem]:
        return self.store.list_flame_pool_items(agent_id=agent_id, state=state)

    def list_runs(self, agent_id: str) -> list[ReflectionBatchRun]:
        runs = self.store.list_flame_runs(agent_id=agent_id)
        return sorted(runs, key=lambda row: row.created_at, reverse=True)

    def status(self, agent_id: str) -> FlameStatus:
        agent = self.store.load_agent(agent_id)
        pending = self.store.list_flame_pool_items(agent_id=agent_id, state=FlamePoolState.PENDING)
        oldest_age = None
        if pending:
            oldest = min(item.created_at for item in pending)
            oldest_age = max(0, int((utc_now() - oldest).total_seconds()))
        runs = self.list_runs(agent_id)
        last = runs[0] if runs else None
        return FlameStatus(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            pending_pool_items=len(pending),
            oldest_pending_age_seconds=oldest_age,
            last_run_state=None if last is None else last.state,
            last_run_at=None if last is None else last.updated_at,
        )

    def _build_session_record(self, agent_id: str, session_id: str) -> SessionRecord:
        events = self.store.load_events(session_id)
        if not events:
            raise ValueError("session_not_found")
        initial_input = ""
        final_output = ""
        feedbacks: list[str] = []
        exchange_log: list[dict[str, str]] = []
        current_output = ""
        accepted_at = utc_now()
        tenant_id = events[0].tenant_id
        for event in events:
            if event.type == EventType.INPUT and not initial_input:
                initial_input = str(event.payload.get("input", ""))
            elif event.type == EventType.AGENT_OUTPUT:
                current_output = str(event.payload.get("content", ""))
                final_output = current_output
            elif event.type == EventType.FEEDBACK:
                fb = str(event.payload.get("feedback", "")).strip()
                if fb:
                    feedbacks.append(fb)
                    exchange_log.append({"agent_output": current_output, "human_feedback": fb})
            elif event.type == EventType.ACCEPTANCE:
                accepted_at = event.created_at
        return SessionRecord(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            initial_input=initial_input,
            exchange_log=exchange_log,
            final_output=final_output,
            human_feedback_present=bool(feedbacks),
            timestamp=accepted_at,
        )

    def _extract_features(self, record: SessionRecord) -> list[ExtractedItem]:
        if self._should_use_openai():
            try:
                return self._extract_features_openai(record)
            except Exception as exc:
                # Strict drop in OpenAI mode when extraction response is malformed/invalid.
                self.metrics and self.metrics.inc("flame_extraction_validation_failed")
                message = str(exc)
                if "provider_error:" in message:
                    self.metrics and self.metrics.inc("flame_extraction_provider_parse_failed")
                else:
                    self.metrics and self.metrics.inc("flame_extraction_schema_validation_failed")
                return []
        if not record.human_feedback_present:
            return [
                ExtractedItem(
                    session_id=record.session_id,
                    agent_id=record.agent_id,
                    tenant_id=record.tenant_id,
                    type=ExtractedType.EXPERIENCE,
                    content="Completed a user-requested task and delivered a final response.",
                    human_feedback_weight=0.15,
                    source_feedback_snippets=[],
                )
            ]
        rows: list[ExtractedItem] = []
        for pair in record.exchange_log:
            feedback = pair.get("human_feedback", "").strip()
            if not feedback:
                continue
            rows.append(
                ExtractedItem(
                    session_id=record.session_id,
                    agent_id=record.agent_id,
                    tenant_id=record.tenant_id,
                    type=ExtractedType.LEARNING_POINT,
                    content=self._sanitize_behavior_text(feedback),
                    human_feedback_weight=0.85,
                    source_feedback_snippets=[feedback[:240]],
                )
            )
        if not rows:
            rows.append(
                ExtractedItem(
                    session_id=record.session_id,
                    agent_id=record.agent_id,
                    tenant_id=record.tenant_id,
                    type=ExtractedType.EXPERIENCE,
                    content="Completed a user-requested task and delivered a final response.",
                    human_feedback_weight=0.15,
                    source_feedback_snippets=[],
                )
            )
        return rows

    def _extract_features_openai(self, record: SessionRecord) -> list[ExtractedItem]:
        mode = "learning_point" if self._has_usable_feedback(record.exchange_log) else "experience"
        payload = {
            "mode": mode,
            "session_id": record.session_id,
            "initial_input": record.initial_input,
            "exchange_log": record.exchange_log,
            "final_output": record.final_output,
            "rule": "Extract high-level behavioral patterns only. Do not include task-specific data or content details.",
            "schema": {
                "items": [
                    {
                        "type": "experience|learning_point",
                        "content": "string",
                        "human_feedback_weight": "0..1",
                        "source_feedback_snippets": ["string"],
                    }
                ]
            },
        }
        cfg = getattr(self.runtime, "config", None)
        model = getattr(cfg, "flame_extraction_model", "gpt-4.1-mini")
        out = self._openai_json_call(
            system=FLAME_EXTRACTION_SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=True),
            model=model,
            agent_id=record.agent_id,
            session_id=record.session_id,
            operation_bucket="flame_extraction",
        )
        normalized_items = self._validate_extraction_output(out=out, expected_mode=mode, exchange_log=record.exchange_log)
        rows: list[ExtractedItem] = []
        for item in normalized_items:
            rows.append(
                ExtractedItem(
                    session_id=record.session_id,
                    agent_id=record.agent_id,
                    tenant_id=record.tenant_id,
                    type=ExtractedType(item["type"]),
                    content=self._sanitize_behavior_text(item["content"]),
                    human_feedback_weight=item["human_feedback_weight"],
                    source_feedback_snippets=item["source_feedback_snippets"],
                )
            )
        return rows

    @staticmethod
    def _has_usable_feedback(exchange_log: list[dict[str, str]]) -> bool:
        for row in exchange_log:
            if str(row.get("human_feedback", "")).strip():
                return True
        return False

    def _validate_extraction_output(
        self,
        *,
        out: dict[str, Any],
        expected_mode: str,
        exchange_log: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        if not isinstance(out, dict):
            raise ValueError("invalid_extraction_output:non_object")
        items = out.get("items", [])
        if not isinstance(items, list):
            raise ValueError("invalid_extraction_output:items_not_array")
        mode = "learning_point" if self._has_usable_feedback(exchange_log) else "experience"
        if expected_mode != mode:
            mode = expected_mode
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"invalid_extraction_output:item_{idx}_not_object")
            type_raw = str(item.get("type", "")).strip().lower()
            if type_raw not in {"experience", "learning_point"}:
                raise ValueError(f"invalid_extraction_output:item_{idx}_bad_type")
            content = str(item.get("content", "")).strip()
            if not content:
                raise ValueError(f"invalid_extraction_output:item_{idx}_empty_content")
            weight_raw = item.get("human_feedback_weight")
            try:
                weight = float(weight_raw)
            except Exception as exc:
                raise ValueError(f"invalid_extraction_output:item_{idx}_bad_weight") from exc
            if weight < 0.0 or weight > 1.0:
                raise ValueError(f"invalid_extraction_output:item_{idx}_weight_range")
            snippets_raw = item.get("source_feedback_snippets", [])
            if snippets_raw is None:
                snippets_raw = []
            if not isinstance(snippets_raw, list):
                raise ValueError(f"invalid_extraction_output:item_{idx}_bad_snippets")
            snippets = [str(v) for v in snippets_raw if str(v).strip()]
            if mode == "experience":
                normalized.append(
                    {
                        "type": "experience",
                        "content": content,
                        "human_feedback_weight": 0.0,
                        "source_feedback_snippets": [],
                    }
                )
            else:
                normalized.append(
                    {
                        "type": type_raw,
                        "content": content,
                        "human_feedback_weight": weight,
                        "source_feedback_snippets": snippets,
                    }
                )
        if mode == "learning_point" and not any(row["human_feedback_weight"] > 0.0 for row in normalized):
            raise ValueError("invalid_extraction_output:learning_point_requires_positive_weight")
        return normalized

    def _run_reflection(self, agent_id: str, trigger_reason: str) -> ReflectionBatchRun:
        agent = self.store.load_agent(agent_id)
        pending = self.store.list_flame_pool_items(agent_id=agent_id, state=FlamePoolState.PENDING)
        run = ReflectionBatchRun(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            trigger_reason=trigger_reason,  # type: ignore[arg-type]
            state=FlameRunState.SKIPPED,
            pool_item_ids=[item.pool_item_id for item in pending],
            reflection_ids=[],
            cluster_count=0,
            extraction_prompt_version=FLAME_EXTRACTION_PROMPT_VERSION,
            extraction_prompt_hash=hashlib.sha256(FLAME_EXTRACTION_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            reflection_prompt_version=FLAME_REFLECTION_PROMPT_VERSION,
            reflection_prompt_hash=hashlib.sha256(FLAME_REFLECTION_SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
            updated_at=utc_now(),
        )
        if not pending:
            self.store.save_flame_run(run)
            return run
        try:
            groups = self._group_pool_items(pending, trigger_reason=trigger_reason)
            reflections: list[ReflectionItem] = []
            for group in groups:
                reflections.extend(self._extract_reflections(group=group, agent_id=agent_id, tenant_id=agent.tenant_id))
            for reflection in reflections:
                self.memory.create(
                    agent_id=agent_id,
                    content=reflection.content,
                    summary=reflection.content[:180],
                    tags=["flame", "reflection"],
                    memory_type=MemoryType.FEEDBACK if reflection.human_feedback_weighted else MemoryType.SEMANTIC,
                    confidence=reflection.confidence,
                    metadata={
                        "reflection_id": reflection.reflection_id,
                        "derived_from": reflection.derived_from,
                        "human_feedback_weighted": reflection.human_feedback_weighted,
                        "confidence": reflection.confidence,
                        "source_snippets_ref": "flame_pool",
                        "created_by": "flame_reflection",
                    },
                )
            self.store.delete_flame_pool_items([item.pool_item_id for item in pending])
            run.state = FlameRunState.SUCCESS
            run.reflection_ids = [item.reflection_id for item in reflections]
            run.cluster_count = len(groups)
            run.updated_at = utc_now()
            self.store.save_flame_run(run)
            self.metrics and self.metrics.inc("flame_runs_success")
            return run
        except Exception as exc:
            run.state = FlameRunState.FAILED
            run.error = str(exc)
            run.updated_at = utc_now()
            self.store.save_flame_run(run)
            self.metrics and self.metrics.inc("flame_runs_failed")
            raise

    def _group_pool_items(self, items: list[PoolItem], trigger_reason: str) -> list[list[PoolItem]]:
        if trigger_reason != "size" or len(items) < 2:
            return [items]
        try:
            import hdbscan
            import numpy as np
        except Exception as exc:
            raise RuntimeError("hdbscan_required_for_size_trigger") from exc
        vectors = np.array([item.embedding for item in items], dtype=float)
        labels = hdbscan.HDBSCAN(min_cluster_size=2, min_samples=1).fit_predict(vectors)
        grouped: dict[int, list[PoolItem]] = {}
        noise_idx = 1000000
        for idx, label in enumerate(labels):
            key = int(label)
            if key < 0:
                key = noise_idx
                noise_idx += 1
            grouped.setdefault(key, []).append(items[idx])
        return list(grouped.values()) if grouped else [items]

    def _extract_reflections(self, group: list[PoolItem], agent_id: str, tenant_id: str) -> list[ReflectionItem]:
        if self._should_use_openai():
            try:
                return self._extract_reflections_openai(group, agent_id=agent_id, tenant_id=tenant_id)
            except Exception:
                pass
        content = self._build_reflection_content(group)
        content = self._cap_text(content, max_chars=FLAME_REFLECTION_CONTENT_MAX_CHARS, metric_name="flame_reflection_content_truncated")
        confidence = max(0.0, min(1.0, sum(item.human_feedback_weight for item in group) / max(1, len(group))))
        weighted = any(item.human_feedback_weight >= 0.6 for item in group)
        return [
            ReflectionItem(
                agent_id=agent_id,
                tenant_id=tenant_id,
                content=content,
                derived_from=sorted(set(item.session_id for item in group)),
                human_feedback_weighted=weighted,
                confidence=confidence,
            )
        ]

    def _extract_reflections_openai(self, group: list[PoolItem], agent_id: str, tenant_id: str) -> list[ReflectionItem]:
        payload = {
            "items": [
                {
                    "session_id": item.session_id,
                    "type": item.extracted_type.value,
                    "content": item.content,
                    "human_feedback_weight": item.human_feedback_weight,
                }
                for item in group
            ],
            "goal": "Return high-level behavioral reflections only; no task-specific data.",
            "schema": {
                "reflections": [
                    {
                        "content": "string",
                        "confidence": "0..1",
                        "human_feedback_weighted": "boolean",
                    }
                ]
            },
        }
        cfg = getattr(self.runtime, "config", None)
        model = getattr(cfg, "flame_reflection_model", "gpt-4.1-mini")
        session_ids = sorted(set(item.session_id for item in group))
        out = self._openai_json_call(
            system=FLAME_REFLECTION_SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=True),
            model=model,
            agent_id=agent_id,
            session_id=session_ids[0] if session_ids else None,
            operation_bucket="flame_reflection",
        )
        if not isinstance(out, dict):
            raise ValueError("invalid_reflection_output:non_object")
        rows = out.get("reflections", [])
        if not isinstance(rows, list):
            raise ValueError("invalid_reflection_output:reflections_not_array")
        result: list[ReflectionItem] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid_reflection_output:item_not_object")
            content = str(row.get("content", "")).strip()
            if not content:
                raise ValueError("invalid_reflection_output:item_empty_content")
            confidence_raw = row.get("confidence")
            try:
                confidence = float(confidence_raw)
            except Exception as exc:
                raise ValueError("invalid_reflection_output:item_bad_confidence") from exc
            if confidence < 0.0 or confidence > 1.0:
                raise ValueError("invalid_reflection_output:item_confidence_range")
            human_feedback_weighted_raw = row.get("human_feedback_weighted")
            if not isinstance(human_feedback_weighted_raw, bool):
                raise ValueError("invalid_reflection_output:item_bad_weighted_flag")
            if confidence < 0.2:
                continue
            result.append(
                ReflectionItem(
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    content=self._cap_text(
                        self._sanitize_behavior_text(content),
                        max_chars=FLAME_REFLECTION_CONTENT_MAX_CHARS,
                        metric_name="flame_reflection_content_truncated",
                    ),
                    derived_from=session_ids,
                    human_feedback_weighted=human_feedback_weighted_raw,
                    confidence=confidence,
                )
            )
        return result

    def _should_trigger(self, agent_id: str, force: bool) -> tuple[bool, str]:
        pending = self.store.list_flame_pool_items(agent_id=agent_id, state=FlamePoolState.PENDING)
        if not pending:
            return False, "none"
        if force:
            return True, "force"
        if len(pending) >= self.pool_size_trigger:
            return True, "size"
        oldest = min(item.created_at for item in pending)
        if oldest <= utc_now() - timedelta(hours=self.time_trigger_hours):
            return True, "time"
        return False, "none"

    def _build_reflection_content(self, group: list[PoolItem]) -> str:
        ordered = sorted(group, key=lambda row: row.human_feedback_weight, reverse=True)
        top = ordered[0]
        if top.extracted_type == ExtractedType.EXPERIENCE:
            return "Maintain consistent response quality and preserve successful completion behavior across similar sessions."
        source = top.source_feedback_snippets[0] if top.source_feedback_snippets else top.content
        return f"User preference pattern: {self._sanitize_behavior_text(source)}"

    @staticmethod
    def _sanitize_behavior_text(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = re.sub(r"\b(session|ticket|task|csv|json|flask|sql)\b", "workflow", cleaned, flags=re.IGNORECASE)
        if not cleaned:
            return "Prefer concise, direct, behavior-aligned responses."
        return cleaned

    def _cap_text(self, text: str, *, max_chars: int, metric_name: str) -> str:
        cleaned = str(text).strip()
        if len(cleaned) <= max_chars:
            return cleaned
        cut = cleaned[:max_chars].rstrip()
        if len(cut) > 1 and cut[-1] not in ".!?":
            cut = cut.rstrip(" ,;:") + "."
            if len(cut) > max_chars:
                cut = cut[:max_chars].rstrip()
                if cut and cut[-1] not in ".!?":
                    cut = cut[:-1].rstrip() + "."
        self.metrics and self.metrics.inc(metric_name)
        return cut

    @staticmethod
    def _embed(content: str, dims: int = 24) -> list[float]:
        data = hashlib.sha256(content.encode("utf-8")).digest()
        out: list[float] = []
        for i in range(dims):
            b = data[i % len(data)]
            out.append((float(b) / 255.0) * 2.0 - 1.0)
        return out

    def _should_use_openai(self) -> bool:
        cfg = getattr(self.runtime, "config", None)
        if cfg is None:
            return False
        return bool(getattr(cfg, "mode", "local") == "openai" and getattr(cfg, "openai_api_key", None))

    def _openai_json_call(
        self,
        system: str,
        user: str,
        model: str,
        agent_id: str,
        session_id: str | None,
        operation_bucket: str,
    ) -> dict[str, Any]:
        cfg = getattr(self.runtime, "config", None)
        if cfg is None or not getattr(cfg, "openai_api_key", None):
            raise RuntimeError("runtime_config_error")
        base_url = (getattr(cfg, "openai_base_url", None) or "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "text": {"format": {"type": "json_object"}},
        }
        started = utc_now()
        with httpx.Client(timeout=float(getattr(cfg, "openai_timeout_ms", 20000)) / 1000.0) as client:
            resp = client.post(
                f"{base_url}/responses",
                headers={"Authorization": f"Bearer {cfg.openai_api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        body = resp.json()
        self._record_openai_usage(
            agent_id=agent_id,
            session_id=session_id,
            model=model,
            operation_bucket=operation_bucket,
            payload=payload,
            response_body=body,
            started_at=started,
        )
        text = body.get("output_text")
        if not isinstance(text, str) or not text.strip():
            text = self._extract_output_text(body)
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("provider_error:invalid_json")
        return parsed

    @staticmethod
    def _extract_output_text(body: dict[str, Any]) -> str:
        output = body.get("output")
        if isinstance(output, list):
            for item in output:
                content = item.get("content") if isinstance(item, dict) else None
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        text = str(part["text"]).strip()
                        if text:
                            return text
        raise ValueError("provider_error:missing_output_text")

    def _record_openai_usage(
        self,
        *,
        agent_id: str,
        session_id: str | None,
        model: str,
        operation_bucket: str,
        payload: dict[str, Any],
        response_body: dict[str, Any],
        started_at: datetime,
    ) -> None:
        if self.usage_tracker is None:
            return
        try:
            agent = self.store.load_agent(agent_id)
        except Exception:
            return
        usage = response_body.get("usage") or {}
        latency_ms = max(0, int((utc_now() - started_at).total_seconds() * 1000))
        request_bytes = len(json.dumps(payload, ensure_ascii=True).encode("utf-8"))
        try:
            record_usage_and_cost(
                usage_tracker=self.usage_tracker,
                capabilities=self.capabilities,
                agent=agent,
                session_id=session_id,
                operation_bucket=operation_bucket,  # type: ignore[arg-type]
                model=model,
                request_bytes=request_bytes,
                latency_ms=latency_ms,
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
                reasoning_tokens=int(usage.get("reasoning_tokens", 0) or 0),
                total_tokens=int(usage.get("total_tokens", 0) or 0),
            )
        except Exception:
            # Tracking should never break learning.
            self.metrics and self.metrics.inc("flame_usage_tracking_failed")
