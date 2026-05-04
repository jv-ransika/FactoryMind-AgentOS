from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_os import AgentOS, AgentTier, EventType, StorageMode
from agent_os.storage import postgres as pg_storage


@dataclass(frozen=True)
class Scenario:
    phase: str
    prompt: str
    feedback_type: str  # detailed|short
    feedback_text: str | None


RARE_TERMS = [
    "assurance case",
    "control inheritance",
    "risk appetite threshold",
    "residual risk envelope",
    "governance attestation",
    "policy-as-code",
    "compensating control",
    "control objective traceability",
    "operational resilience",
    "lineage integrity",
    "evidence provenance",
    "segregation of duties",
]

STYLE_MARKERS = ["assumptions:", "decision:", "controls:", "risks:", "mitigations:"]

RETRIEVAL_PROBES = [
    "Write with assurance case language and explicit control objective traceability.",
    "Use residual risk envelope and risk appetite threshold terminology.",
    "Prioritize governance attestation and evidence provenance in recommendations.",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _acceptance_timestamp(agent_os: AgentOS, session_id: str) -> str | None:
    for event in reversed(agent_os.sessions.events(session_id)):
        if event.type == EventType.ACCEPTANCE:
            return event.created_at.isoformat()
    return None


def _tone_score(text: str) -> dict:
    lower = text.lower()
    rare_hits = sum(1 for term in RARE_TERMS if term in lower)
    marker_hits = sum(1 for marker in STYLE_MARKERS if marker in lower)
    rare_component = min(1.0, rare_hits / 4.0)
    marker_component = min(1.0, marker_hits / 3.0)
    score = round((0.7 * rare_component) + (0.3 * marker_component), 4)
    return {
        "score": score,
        "rare_hits": rare_hits,
        "marker_hits": marker_hits,
    }


def _structure_score(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_lines = [line for line in lines if line.startswith("- ") or line.startswith("* ") or line[:2].isdigit()]
    has_risk = "risk" in text.lower()
    has_mitigation = "mitigat" in text.lower()
    has_decision = "decision" in text.lower() or "recommend" in text.lower()
    score = 0.0
    score += 0.4 if len(bullet_lines) >= 3 else 0.0
    score += 0.2 if has_risk else 0.0
    score += 0.2 if has_mitigation else 0.0
    score += 0.2 if has_decision else 0.0
    return {
        "score": round(score, 4),
        "bullet_count": len(bullet_lines),
        "has_risk": has_risk,
        "has_mitigation": has_mitigation,
        "has_decision": has_decision,
    }


def _feedback_uptake_latency(rows: list[dict]) -> int | None:
    for row in rows:
        if row["feedback_present"] and row["tone"]["score"] >= 0.55 and row["structure"]["score"] >= 0.6:
            return int(row["condition_session_index"])
    return None


def _detailed_feedback(term_hint: str) -> str:
    return (
        "Use a distinctive governance-forward voice and avoid generic proposal phrasing. "
        "Anchor the response with explicit assumptions, a decision statement, and control-oriented mitigation language. "
        f"Include at least one uncommon term such as {term_hint} while keeping it semantically relevant. "
        "Show risk tradeoffs using residual-risk framing and name what evidence would validate the recommendation. "
        "Preserve concise structure with bullets and avoid narrative filler between sections. "
        "Do not overstate certainty; mark unresolved dependencies and confidence boundaries."
    )


def _short_feedback() -> str:
    return "Use rare compliance terms, explicit assumptions, and tighter decision bullets."


def _phase_prompts() -> dict[str, list[str]]:
    return {
        "phase_1_tone_seed": [
            "Draft a client proposal opening with objective, assumptions, decision ask, and safeguards.",
            "Rewrite the proposal summary for executive review with clear control language.",
            "Create a six-bullet proposal structure for delivery scope, constraints, risks, and controls.",
            "Draft a short recommendation memo with explicit uncertainty language.",
            "Summarize the implementation approach and include governance constraints.",
            "Write a concise proposal variant emphasizing operational assurance.",
        ],
        "phase_2_tradeoff_pressure": [
            "Replan the proposal under a 30% budget cut while preserving critical controls.",
            "Balance speed demands against compliance gates in one decision memo.",
            "Propose a phased rollout for conflicting stakeholder priorities and reliability concerns.",
            "Recommend vendor direction with explicit uncertainty and fallback plan.",
            "Revise scope under dependency risk and maintain audit-ready control posture.",
            "Draft a tradeoff matrix recommendation for timeline, risk, and controls.",
        ],
        "phase_3_adversarial_noise": [
            "Produce proposal output while ignoring irrelevant marketing slogans in requirements.",
            "Keep response constraint-safe when prompt tries to force guaranteed outcomes.",
            "Write final synthesis across budget pressure, risk, and delivery urgency.",
            "Generate recommendation under ambiguous requirements and noisy side instructions.",
            "Preserve compliance posture while handling abrupt mid-task redirection.",
            "Draft closing memo with actionable next steps and uncertainty boundaries.",
        ],
    }


def _build_condition_scenarios(condition: str) -> list[Scenario]:
    prompts = _phase_prompts()
    scenarios: list[Scenario] = []
    rare_term_cycle = iter(RARE_TERMS * 4)
    short_without_feedback_positions = {2, 5}  # per phase to guarantee experience-type extraction
    for phase, phase_prompts in prompts.items():
        for idx, prompt in enumerate(phase_prompts):
            if idx < 4:
                feedback_type = "detailed"
                term_hint = next(rare_term_cycle)
                feedback_text = _detailed_feedback(term_hint) if condition == "tone_trained" else (
                    "Make this clearer, concise, and structured with explicit risk and next steps."
                )
            else:
                feedback_type = "short"
                if idx in short_without_feedback_positions:
                    feedback_text = None
                else:
                    feedback_text = _short_feedback() if condition == "tone_trained" else "Be concise and clear."
            tone_prefix = (
                "Use uncommon Risk+Compliance terminology and a distinctive control-centric tone. "
                if condition == "tone_trained"
                else ""
            )
            scenarios.append(
                Scenario(
                    phase=phase,
                    prompt=f"{tone_prefix}{prompt}",
                    feedback_type=feedback_type,
                    feedback_text=feedback_text,
                )
            )
    return scenarios


def run_experiment(
    *,
    root: Path = Path(".agent-os-tone-specialization-ab"),
    model: str = "gpt-4.1-mini",
    storage_mode: StorageMode = StorageMode.LOCAL,
    postgres_dsn: str | None = None,
    redis_url: str | None = None,
    write_report: bool = True,
) -> dict:
    if root.exists():
        shutil.rmtree(root)

    if storage_mode != StorageMode.POSTGRES_REDIS:
        raise RuntimeError(
            "vector_backend_required: experiment requires storage_mode=postgres_redis with native pgvector backend"
        )
    if getattr(pg_storage, "Vector", None) is None:
        raise RuntimeError(
            "vector_backend_required: pgvector_python_package_missing for experiment preflight"
        )

    app = AgentOS.load(
        root=root,
        runtime_mode="openai",
        storage_mode=storage_mode,
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
    )
    conditions = {
        "baseline": app.create_agent(
            agent_id="tone-baseline-agent",
            goal="Write proposal responses with clear structure.",
            model=model,
            tenant_id="default",
            agent_tier=AgentTier.SELF_LEARNING_AGENT,
        ),
        "tone_trained": app.create_agent(
            agent_id="tone-specialized-agent",
            goal="Write proposal responses in a distinctive Risk+Compliance voice with explicit controls.",
            model=model,
            tenant_id="default",
            agent_tier=AgentTier.SELF_LEARNING_AGENT,
        ),
    }
    scenarios_by_condition = {
        "baseline": _build_condition_scenarios("baseline"),
        "tone_trained": _build_condition_scenarios("tone_trained"),
    }

    sessions: list[dict] = []
    extracted_features: list[dict] = []
    reflection_runs: list[dict] = []
    memories_created: list[dict] = []
    retrieval_probes: list[dict] = []

    hard_failures: list[str] = []
    run_status = "success"
    try:
        for condition_name, agent in conditions.items():
            condition_scenarios = scenarios_by_condition[condition_name]
            assert len(condition_scenarios) == 18, "each_condition_requires_18_sessions"
            for condition_idx, scenario in enumerate(condition_scenarios, start=1):
                session = app.sessions.init(agent.id, scenario.prompt)
                output = app.sessions.run(session.session_id)
                if scenario.feedback_text:
                    app.sessions.feedback(session.session_id, scenario.feedback_text)
                app.sessions.accept(session.session_id)

                tone = _tone_score(output.content)
                structure = _structure_score(output.content)

                sessions.append(
                    {
                        "condition": condition_name,
                        "phase": scenario.phase,
                        "condition_session_index": condition_idx,
                        "session_id": session.session_id,
                        "input": scenario.prompt,
                        "output_type": output.type.value,
                        "output_content": output.content,
                        "feedback_type": scenario.feedback_type,
                        "feedback_present": bool(scenario.feedback_text),
                        "feedback_text": scenario.feedback_text,
                        "accepted_at": _acceptance_timestamp(app, session.session_id),
                        "tone": tone,
                        "structure": structure,
                    }
                )

                if condition_idx % 3 != 0:
                    continue

                checkpoint = condition_idx // 3
                pool_before = app.flame.list_pool(agent.id)
                for item in pool_before:
                    extracted_features.append(
                        {
                            "condition": condition_name,
                            "checkpoint": checkpoint,
                            "pool_item_id": item.pool_item_id,
                            "session_id": item.session_id,
                            "type": item.extracted_type.value,
                            "content": item.content,
                            "human_feedback_weight": item.human_feedback_weight,
                            "source_feedback_snippets": list(item.source_feedback_snippets),
                        }
                    )

                memory_ids_before = {m.memory_id for m in app.memory.list(agent.id)}
                runs = app.flame.trigger(agent_id=agent.id, force=True)
                run = runs[-1] if runs else None
                pool_after = app.flame.list_pool(agent.id)
                memories_after = app.memory.list(agent.id)
                new_reflection_memories = [
                    m for m in memories_after if m.memory_id not in memory_ids_before and m.metadata.get("created_by") == "flame_reflection"
                ]

                reflection_runs.append(
                    {
                        "condition": condition_name,
                        "checkpoint": checkpoint,
                        "run_id": None if run is None else run.run_id,
                        "state": None if run is None else run.state.value,
                        "trigger_reason": None if run is None else run.trigger_reason,
                        "cluster_count": None if run is None else run.cluster_count,
                        "pool_count_before": len(pool_before),
                        "pool_count_after": len(pool_after),
                        "reflection_ids": [] if run is None else list(run.reflection_ids),
                        "error": None if run is None else run.error,
                        "extraction_prompt_version": None if run is None else run.extraction_prompt_version,
                        "extraction_prompt_hash": None if run is None else run.extraction_prompt_hash,
                        "reflection_prompt_version": None if run is None else run.reflection_prompt_version,
                        "reflection_prompt_hash": None if run is None else run.reflection_prompt_hash,
                        "new_flame_memory_count": len(new_reflection_memories),
                    }
                )

                for memory in new_reflection_memories:
                    memories_created.append(
                        {
                            "condition": condition_name,
                            "checkpoint": checkpoint,
                            "memory_id": memory.memory_id,
                            "confidence": memory.confidence,
                            "content": memory.content,
                            "metadata": {
                                "created_by": memory.metadata.get("created_by"),
                                "reflection_id": memory.metadata.get("reflection_id"),
                                "derived_from": memory.metadata.get("derived_from"),
                                "human_feedback_weighted": memory.metadata.get("human_feedback_weighted"),
                                "confidence": memory.metadata.get("confidence"),
                            },
                        }
                    )

                for query in RETRIEVAL_PROBES:
                    retrieved = app.memory.retrieve(agent.id, query, limit=5)
                    retrieval_probes.append(
                        {
                            "condition": condition_name,
                            "checkpoint": checkpoint,
                            "query": query,
                            "result_count": len(retrieved),
                            "results": [
                                {
                                    "memory_id": row.item.memory_id,
                                    "score": row.retrieval.score,
                                    "memory_content": row.item.content,
                                    "created_by": row.item.metadata.get("created_by"),
                                    "is_flame_reflection": row.item.metadata.get("created_by") == "flame_reflection",
                                }
                                for row in retrieved
                            ],
                        }
                    )
    except Exception as exc:
        run_status = "failed"
        hard_failures.append(str(exc))

    condition_summary: dict[str, dict] = {}
    for condition_name in ("baseline", "tone_trained"):
        condition_sessions = [s for s in sessions if s["condition"] == condition_name]
        condition_features = [f for f in extracted_features if f["condition"] == condition_name]
        condition_runs = [r for r in reflection_runs if r["condition"] == condition_name]
        condition_retrieval = [r for r in retrieval_probes if r["condition"] == condition_name]
        tone_scores = [row["tone"]["score"] for row in condition_sessions]
        structure_scores = [row["structure"]["score"] for row in condition_sessions]
        retrieval_scores = [
            result["score"]
            for probe in condition_retrieval
            for result in probe["results"]
            if result["is_flame_reflection"]
        ]
        tone_reflection_hit_count = sum(
            1
            for probe in condition_retrieval
            if any(result["is_flame_reflection"] for result in probe["results"])
        )
        condition_summary[condition_name] = {
            "session_count": len(condition_sessions),
            "accepted_session_count": sum(1 for s in condition_sessions if s["accepted_at"] is not None),
            "feature_experience_count": sum(1 for f in condition_features if f["type"] == "experience"),
            "feature_learning_point_count": sum(1 for f in condition_features if f["type"] == "learning_point"),
            "reflection_run_success_count": sum(1 for r in condition_runs if r["state"] == "success"),
            "reflection_run_failure_count": sum(1 for r in condition_runs if r["state"] != "success"),
            "avg_tone_score": round(sum(tone_scores) / max(1, len(tone_scores)), 4),
            "avg_structure_score": round(sum(structure_scores) / max(1, len(structure_scores)), 4),
            "feedback_uptake_latency": _feedback_uptake_latency(condition_sessions),
            "avg_reflection_retrieval_score": round(sum(retrieval_scores) / max(1, len(retrieval_scores)), 4) if retrieval_scores else 0.0,
            "tone_probe_reflection_hit_count": tone_reflection_hit_count,
            "retrieval_probe_count": len(condition_retrieval),
        }

    baseline = condition_summary["baseline"]
    tone = condition_summary["tone_trained"]
    ab_delta = {
        "tone_score_delta": round(tone["avg_tone_score"] - baseline["avg_tone_score"], 4),
        "structure_score_delta": round(tone["avg_structure_score"] - baseline["avg_structure_score"], 4),
        "retrieval_score_delta": round(tone["avg_reflection_retrieval_score"] - baseline["avg_reflection_retrieval_score"], 4),
        "feedback_uptake_latency_delta": (
            None
            if tone["feedback_uptake_latency"] is None or baseline["feedback_uptake_latency"] is None
            else tone["feedback_uptake_latency"] - baseline["feedback_uptake_latency"]
        ),
    }

    summary = {
        "condition_summary": condition_summary,
        "ab_delta": ab_delta,
        "passes": {
            "tone_beats_baseline": ab_delta["tone_score_delta"] >= 0.12,
            "faster_or_equal_feedback_uptake": (
                ab_delta["feedback_uptake_latency_delta"] is not None and ab_delta["feedback_uptake_latency_delta"] <= 0
            ),
            "better_reflection_retrieval": ab_delta["retrieval_score_delta"] > 0.0,
        },
    }

    retrieval_readiness = {
        condition: (
            condition_summary[condition]["tone_probe_reflection_hit_count"] > 0
            and condition_summary[condition]["avg_reflection_retrieval_score"] > 0.0
        )
        for condition in ("baseline", "tone_trained")
    }

    metrics_snapshot: dict[str, Any] = {}
    try:
        metrics_path = root / "metrics" / "metrics.json"
        if metrics_path.exists():
            metrics_snapshot = json.loads(metrics_path.read_text(encoding="utf-8"))
    except Exception:
        metrics_snapshot = {}

    usage_rollup: dict[str, Any] = {"total_cost_usd": 0.0, "by_agent": {}, "by_bucket": {}}
    usage_path = root / "usage" / "costs.jsonl"
    if usage_path.exists():
        costs = [json.loads(line) for line in usage_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        usage_rollup["total_cost_usd"] = round(sum(float(row.get("estimated_cost_usd", 0.0) or 0.0) for row in costs), 6)
        by_agent: dict[str, float] = {}
        by_bucket: dict[str, float] = {}
        for row in costs:
            agent = str(row.get("agent_id", "unknown"))
            bucket = str(row.get("operation_bucket", "unknown"))
            value = float(row.get("estimated_cost_usd", 0.0) or 0.0)
            by_agent[agent] = by_agent.get(agent, 0.0) + value
            by_bucket[bucket] = by_bucket.get(bucket, 0.0) + value
        usage_rollup["by_agent"] = {k: round(v, 6) for k, v in by_agent.items()}
        usage_rollup["by_bucket"] = {k: round(v, 6) for k, v in by_bucket.items()}

    diagnostics = {
        "accepted_sessions": sum(1 for s in sessions if s["accepted_at"] is not None),
        "temp_memory_pool_item_count": len(extracted_features),
        "reflection_run_count": len(reflection_runs),
        "memory_count": len(memories_created),
        "retrieval_probe_count": len(retrieval_probes),
        "retrieval_reflection_hit_count": sum(
            1 for row in retrieval_probes if any(result["is_flame_reflection"] for result in row["results"])
        ),
        "extraction_failure_metrics": {
            "flame_extraction_validation_failed": metrics_snapshot.get("flame_extraction_validation_failed", 0),
            "flame_extraction_provider_parse_failed": metrics_snapshot.get("flame_extraction_provider_parse_failed", 0),
            "flame_extraction_schema_validation_failed": metrics_snapshot.get("flame_extraction_schema_validation_failed", 0),
        },
        "retrieval_readiness": retrieval_readiness,
    }

    session_examples = []
    for condition_name in ("baseline", "tone_trained"):
        rows = [s for s in sessions if s["condition"] == condition_name][:2]
        for row in rows:
            session_examples.append(
                {
                    "condition": condition_name,
                    "session_id": row["session_id"],
                    "phase": row["phase"],
                    "feedback_type": row["feedback_type"],
                    "output_excerpt": row["output_content"][:280],
                }
            )

    root_cause_summary = []
    if diagnostics["temp_memory_pool_item_count"] == 0:
        root_cause_summary.append("no_extracted_items_written_to_temp_pool")
    if diagnostics["memory_count"] == 0:
        root_cause_summary.append("no_reflection_memories_persisted")
    if diagnostics["extraction_failure_metrics"]["flame_extraction_provider_parse_failed"] > 0:
        root_cause_summary.append("provider_parse_failures_detected")
    if diagnostics["extraction_failure_metrics"]["flame_extraction_schema_validation_failed"] > 0:
        root_cause_summary.append("schema_validation_failures_detected")

    vector_backend = "postgres_pgvector"

    report = {
        "meta": {
            "generated_at": _now_iso(),
            "runtime_mode": "openai",
            "model_id": model,
            "root": str(root),
            "storage_mode": storage_mode.value,
            "vector_backend": vector_backend,
            "experiment": {
                "total_sessions": 36,
                "conditions": ["baseline", "tone_trained"],
                "sessions_per_condition": 18,
                "phases": ["phase_1_tone_seed", "phase_2_tradeoff_pressure", "phase_3_adversarial_noise"],
                "feedback_policy": "12_detailed_and_6_short_per_condition",
                "reflection_every_n_sessions": 3,
                "retrieval_probes": RETRIEVAL_PROBES,
            },
        },
        "run_status": run_status,
        "hard_failures": hard_failures,
        "sessions": sessions,
        "extracted_features": extracted_features,
        "reflection_runs": reflection_runs,
        "memories_created": memories_created,
        "retrieval_probes": retrieval_probes,
        "diagnostics": diagnostics,
        "root_cause_summary": root_cause_summary,
        "session_examples": session_examples,
        "costs": usage_rollup,
        "summary": summary,
    }

    structural_errors: list[str] = []
    if len(sessions) != 36:
        structural_errors.append("expected_36_sessions")
    if sum(1 for s in sessions if s["accepted_at"] is not None) != 36:
        structural_errors.append("expected_36_accepted_sessions")
    if not usage_path.exists():
        structural_errors.append("missing_cost_usage_file")
    if structural_errors:
        run_status = "failed"
        hard_failures.extend(structural_errors)
        report["run_status"] = run_status
        report["hard_failures"] = hard_failures
    elif run_status != "failed":
        if root_cause_summary:
            run_status = "partial_failure"
            report["run_status"] = run_status

    if write_report:
        report_dir = root / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "flame_tone_specialization_ab_report.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["meta"]["report_path"] = str(report_path)

    return report


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-4.1-mini"
    storage_mode = StorageMode.LOCAL
    postgres_dsn = None
    redis_url = None
    if len(sys.argv) > 2 and sys.argv[2].lower() == "postgres":
        storage_mode = StorageMode.POSTGRES_REDIS
        postgres_dsn = sys.argv[3] if len(sys.argv) > 3 else "postgresql://postgres@localhost/postgres"
        redis_url = sys.argv[4] if len(sys.argv) > 4 else "redis://localhost:6379/0"
    report = run_experiment(
        model=model,
        storage_mode=storage_mode,
        postgres_dsn=postgres_dsn,
        redis_url=redis_url,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
