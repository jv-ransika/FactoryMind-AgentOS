from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent_os import AgentOS, AgentTier, EventType


@dataclass(frozen=True)
class SessionScenario:
    input_text: str
    feedback: str | None = None


SCENARIOS: list[list[SessionScenario]] = [
    [
        SessionScenario("Draft a proposal intro for an enterprise AI rollout."),
        SessionScenario(
            "Rewrite this proposal section for executive readability.",
            "Use concise direct tone and short bullet points.",
        ),
        SessionScenario(
            "Provide a client-ready proposal summary with next steps.",
            "Keep formatting crisp and avoid generic filler text.",
        ),
    ],
    [
        SessionScenario("Select top 3 projects for low delivery risk."),
        SessionScenario(
            "Rank project options for next quarter execution.",
            "Prioritize delivery risk and dependency complexity in ranking.",
        ),
        SessionScenario(
            "Recommend one project for immediate kickoff.",
            "Always justify recommendation with explicit risk rationale.",
        ),
    ],
    [
        SessionScenario("Extract keywords from this proposal draft."),
        SessionScenario(
            "Extract operational and risk keywords from project notes.",
            "Include precision-focused keywords and avoid broad vague terms.",
        ),
        SessionScenario(
            "Return final keyword set for project selection and delivery planning.",
            "Ensure coverage includes risk, timeline, and dependencies.",
        ),
    ],
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _acceptance_timestamp(agent_os: AgentOS, session_id: str) -> str | None:
    for event in reversed(agent_os.sessions.events(session_id)):
        if event.type == EventType.ACCEPTANCE:
            return event.created_at.isoformat()
    return None


def run_validation(
    *,
    root: Path = Path(".agent-os-live-check"),
    model: str = "gpt-4.1-mini",
    write_report: bool = True,
) -> dict:
    if root.exists():
        shutil.rmtree(root)

    agent_os = AgentOS.load(root=root, runtime_mode="openai")
    agent = agent_os.create_agent(
        agent_id="flame-live-validator",
        goal="Validate FLAME multi-run learning behavior",
        model=model,
        tenant_id="default",
        agent_tier=AgentTier.SELF_LEARNING_AGENT,
    )

    sessions: list[dict] = []
    extracted_features: list[dict] = []
    reflection_runs: list[dict] = []
    memories_created: list[dict] = []
    created_memory_ids: set[str] = set()

    try:
        for run_index, run_scenarios in enumerate(SCENARIOS, start=1):
            for scenario in run_scenarios:
                session = agent_os.sessions.init(agent.id, scenario.input_text)
                agent_os.sessions.run(session.session_id)
                if scenario.feedback:
                    agent_os.sessions.feedback(session.session_id, scenario.feedback)
                agent_os.sessions.accept(session.session_id)
                sessions.append(
                    {
                        "run_index": run_index,
                        "session_id": session.session_id,
                        "input": scenario.input_text,
                        "feedback_present": bool(scenario.feedback),
                        "accepted_at": _acceptance_timestamp(agent_os, session.session_id),
                    }
                )

            pool_before = agent_os.flame.list_pool(agent.id)
            extracted_features.extend(
                [
                    {
                        "run_index": run_index,
                        "pool_item_id": item.pool_item_id,
                        "session_id": item.session_id,
                        "type": item.extracted_type.value,
                        "content": item.content,
                        "human_feedback_weight": item.human_feedback_weight,
                    }
                    for item in pool_before
                ]
            )

            before_memory_ids = {m.memory_id for m in agent_os.flame.memory.list(agent.id)}
            run_results = agent_os.flame.trigger(agent_id=agent.id, force=True)
            run = run_results[-1] if run_results else None
            after_pool = agent_os.flame.list_pool(agent.id)
            after_memories = agent_os.flame.memory.list(agent.id)
            new_memories = [
                m
                for m in after_memories
                if m.memory_id not in before_memory_ids and m.metadata.get("created_by") == "flame_reflection"
            ]

            reflection_runs.append(
                {
                    "run_index": run_index,
                    "run_id": None if run is None else run.run_id,
                    "trigger_reason": None if run is None else run.trigger_reason,
                    "state": None if run is None else run.state.value,
                    "cluster_count": None if run is None else run.cluster_count,
                    "pool_item_ids": [] if run is None else list(run.pool_item_ids),
                    "reflection_ids": [] if run is None else list(run.reflection_ids),
                    "error": None if run is None else run.error,
                    "pool_count_before": len(pool_before),
                    "pool_count_after": len(after_pool),
                    "new_flame_memory_count": len(new_memories),
                }
            )

            for memory in new_memories:
                created_memory_ids.add(memory.memory_id)
                memories_created.append(
                    {
                        "run_index": run_index,
                        "memory_id": memory.memory_id,
                        "content": memory.content,
                        "confidence": memory.confidence,
                        "metadata": {
                            "created_by": memory.metadata.get("created_by"),
                            "reflection_id": memory.metadata.get("reflection_id"),
                            "derived_from": memory.metadata.get("derived_from"),
                            "human_feedback_weighted": memory.metadata.get("human_feedback_weighted"),
                            "confidence": memory.metadata.get("confidence"),
                        },
                    }
                )

        feature_types = {row["type"] for row in extracted_features}
        reflection_success_count = sum(1 for row in reflection_runs if row["state"] == "success")
        reflection_failure_count = sum(1 for row in reflection_runs if row["state"] != "success")

        summary_counts = {
            "run_count": len(SCENARIOS),
            "session_count": len(sessions),
            "accepted_session_count": len([s for s in sessions if s["accepted_at"] is not None]),
            "experience_count": len([f for f in extracted_features if f["type"] == "experience"]),
            "learning_point_count": len([f for f in extracted_features if f["type"] == "learning_point"]),
            "reflection_run_success_count": reflection_success_count,
            "reflection_run_failure_count": reflection_failure_count,
            "flame_memory_created_count": len(created_memory_ids),
        }

        report = {
            "meta": {
                "generated_at": _now_iso(),
                "runtime_mode": "openai",
                "model_id": model,
                "agent_id": agent.id,
                "root": str(root),
                "total_runs": len(SCENARIOS),
                "total_sessions_planned": len(SCENARIOS) * 3,
            },
            "sessions": sessions,
            "extracted_features": extracted_features,
            "reflection_runs": reflection_runs,
            "memories_created": memories_created,
            "summary_counts": summary_counts,
        }

        # Assertions required by the plan.
        assert summary_counts["accepted_session_count"] == 9, "expected_9_accepted_sessions"
        assert summary_counts["reflection_run_failure_count"] == 0, "all_reflection_runs_must_succeed"
        assert "experience" in feature_types and "learning_point" in feature_types, "both_feature_types_required"
        assert all(row["new_flame_memory_count"] >= 1 for row in reflection_runs), "at_least_one_memory_per_run_required"
        required_metadata_keys = {"created_by", "reflection_id", "derived_from", "human_feedback_weighted", "confidence"}
        for row in memories_created:
            md = row["metadata"]
            assert required_metadata_keys.issubset(set(md.keys())), "missing_required_metadata_keys"
            assert md["created_by"] == "flame_reflection", "invalid_created_by"
            assert md["reflection_id"], "missing_reflection_id"
            assert isinstance(md["derived_from"], list) and md["derived_from"], "missing_derived_from"

        if write_report:
            report_dir = root / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "flame_multi_run_report.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            report["meta"]["report_path"] = str(report_path)

        return report
    except Exception as exc:
        failure_report = {
            "meta": {
                "generated_at": _now_iso(),
                "runtime_mode": "openai",
                "model_id": model,
                "agent_id": agent.id,
                "root": str(root),
            },
            "sessions": sessions,
            "extracted_features": extracted_features,
            "reflection_runs": reflection_runs,
            "memories_created": memories_created,
            "error": str(exc),
        }
        print(json.dumps(failure_report, indent=2))
        raise


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-4.1-mini"
    report = run_validation(model=model)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
