from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from agent_os.protocol import (
    AgentDefinition,
    GateDecisionReport,
    LearningCandidate,
    LearningRun,
    PoolItem,
    ReflectionBatchRun,
    FlamePoolState,
    MemoryItem,
    PromotionMode,
    PromotionPolicy,
    PromotionState,
    RollbackRecord,
    Session,
    SessionEvent,
    SessionStatus,
    SkillDefinition,
    ToolAuditEvent,
    ToolManifest,
    ToolScope,
    ValidationReport,
)


class LocalStore:
    def __init__(self, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.agents_dir = self.root / "agents"
        self.memory_dir = self.root / "memory"
        self.sessions_dir = self.root / "sessions"
        self.skills_dir = self.root / "skills"
        self.skill_bindings_dir = self.root / "skill_bindings"
        self.learning_dir = self.root / "learning"
        self.learning_runs_dir = self.learning_dir / "runs"
        self.learning_candidates_dir = self.learning_dir / "candidates"
        self.learning_reports_dir = self.learning_dir / "reports"
        self.learning_gate_reports_dir = self.learning_dir / "gate_reports"
        self.learning_rollbacks_dir = self.learning_dir / "rollbacks"
        self.flame_dir = self.root / "flame"
        self.flame_pool_dir = self.flame_dir / "pool"
        self.flame_runs_dir = self.flame_dir / "runs"
        self.tools_dir = self.root / "tools"
        self.tools_manifests_dir = self.tools_dir / "manifests"
        self.tools_allowlists_dir = self.tools_dir / "agent_allowlists"
        self.tools_audit_dir = self.tools_dir / "audit"
        self.policy_dir = self.root / "policy"
        self.config_path = self.root / "config.json"

    def init(self) -> None:
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.skill_bindings_dir.mkdir(parents=True, exist_ok=True)
        self.learning_runs_dir.mkdir(parents=True, exist_ok=True)
        self.learning_candidates_dir.mkdir(parents=True, exist_ok=True)
        self.learning_reports_dir.mkdir(parents=True, exist_ok=True)
        self.learning_gate_reports_dir.mkdir(parents=True, exist_ok=True)
        self.learning_rollbacks_dir.mkdir(parents=True, exist_ok=True)
        self.flame_pool_dir.mkdir(parents=True, exist_ok=True)
        self.flame_runs_dir.mkdir(parents=True, exist_ok=True)
        self.tools_manifests_dir.mkdir(parents=True, exist_ok=True)
        self.tools_allowlists_dir.mkdir(parents=True, exist_ok=True)
        self.tools_audit_dir.mkdir(parents=True, exist_ok=True)
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._write_json(self.config_path, {"version": "1.2.0"})

    def save_agent(self, agent: AgentDefinition) -> None:
        self.init()
        self._write_json(self.agent_path(agent.id), agent.model_dump(mode="json"))

    def load_agent(self, agent_id: str) -> AgentDefinition:
        path = self.agent_path(agent_id)
        if not path.exists():
            raise FileNotFoundError(f"Agent not found: {agent_id}")
        return AgentDefinition.model_validate(self._read_json(path))

    def list_agents(self) -> list[AgentDefinition]:
        self.init()
        return [
            AgentDefinition.model_validate(self._read_json(path))
            for path in sorted(self.agents_dir.glob("*.json"))
        ]

    def save_memory(self, memory: MemoryItem) -> None:
        self.init()
        self._write_json(self.memory_path(memory.agent_id, memory.memory_id), memory.model_dump(mode="json"))

    def save_memory_vector(self, agent_id: str, memory_id: str, embedding: list[float]) -> None:
        _ = agent_id
        _ = memory_id
        _ = embedding
        # Local mode does not provide vector retrieval in this iteration.
        return None

    def query_memory_vectors(self, agent_id: str, query_embedding: list[float], limit: int = 5) -> list[tuple[str, float]]:
        _ = agent_id
        _ = query_embedding
        _ = limit
        # Local mode does not provide vector retrieval in this iteration.
        return []

    def load_memory(self, agent_id: str, memory_id: str) -> MemoryItem:
        path = self.memory_path(agent_id, memory_id)
        if not path.exists():
            raise FileNotFoundError(f"Memory not found: {memory_id}")
        return MemoryItem.model_validate(self._read_json(path))

    def list_memories(self, agent_id: str) -> list[MemoryItem]:
        self.init()
        agent_dir = self.memory_dir / agent_id
        if not agent_dir.exists():
            return []
        return [
            MemoryItem.model_validate(self._read_json(path))
            for path in sorted(agent_dir.glob("*.json"))
        ]

    def save_skill(self, skill: SkillDefinition) -> None:
        self.init()
        self._write_json(self.skill_path(skill.skill_id), skill.model_dump(mode="json"))

    def load_skill(self, skill_id: str) -> SkillDefinition:
        path = self.skill_path(skill_id)
        if not path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_id}")
        return SkillDefinition.model_validate(self._read_json(path))

    def list_skills(self) -> list[SkillDefinition]:
        self.init()
        return [
            SkillDefinition.model_validate(self._read_json(path))
            for path in sorted(self.skills_dir.glob("*.json"))
        ]

    def bind_skill(self, agent_id: str, skill_id: str) -> None:
        self.init()
        path = self.skill_binding_path(agent_id)
        existing = self._read_json(path) if path.exists() else {"skill_ids": []}
        skill_ids = [str(value) for value in existing.get("skill_ids", [])]
        if skill_id not in skill_ids:
            skill_ids.append(skill_id)
        self._write_json(path, {"agent_id": agent_id, "skill_ids": skill_ids})

    def list_bound_skill_ids(self, agent_id: str) -> list[str]:
        self.init()
        path = self.skill_binding_path(agent_id)
        if not path.exists():
            return []
        binding = self._read_json(path)
        return [str(value) for value in binding.get("skill_ids", [])]

    def save_tool_manifest(self, manifest: ToolManifest) -> None:
        self.init()
        self._write_json(self.tool_manifest_path(manifest.tool_id), manifest.model_dump(mode="json"))

    def load_tool_manifest(self, tool_id: str) -> ToolManifest:
        path = self.tool_manifest_path(tool_id)
        if not path.exists():
            raise FileNotFoundError(f"Tool not found: {tool_id}")
        return ToolManifest.model_validate(self._read_json(path))

    def list_tool_manifests(self) -> list[ToolManifest]:
        self.init()
        return [
            ToolManifest.model_validate(self._read_json(path))
            for path in sorted(self.tools_manifests_dir.glob("*.json"))
        ]

    def bind_tool(self, agent_id: str, tool_id: str, allow_write: bool = False) -> None:
        self.load_agent(agent_id)
        manifest = self.load_tool_manifest(tool_id)
        path = self.tool_allowlist_path(agent_id)
        data = self._read_json(path) if path.exists() else {"agent_id": agent_id, "tools": []}
        tools = [entry for entry in data.get("tools", []) if isinstance(entry, dict)]
        existing = next((entry for entry in tools if str(entry.get("tool_id")) == tool_id), None)
        entry = {
            "tool_id": tool_id,
            "allow_write": bool(allow_write) and manifest.scope == ToolScope.WRITE,
        }
        if existing is None:
            tools.append(entry)
        else:
            existing.update(entry)
        self._write_json(path, {"agent_id": agent_id, "tools": tools})

    def list_bound_tools(self, agent_id: str) -> list[dict]:
        self.load_agent(agent_id)
        path = self.tool_allowlist_path(agent_id)
        if not path.exists():
            return []
        data = self._read_json(path)
        tools = data.get("tools", [])
        return tools if isinstance(tools, list) else []

    def save_tool_audit(self, audit: ToolAuditEvent) -> None:
        self.init()
        self._write_json(self.tool_audit_path(audit.audit_id), audit.model_dump(mode="json"))

    def list_tool_audits(self, agent_id: str, session_id: str | None = None) -> list[ToolAuditEvent]:
        self.load_agent(agent_id)
        audits = [
            ToolAuditEvent.model_validate(self._read_json(path))
            for path in sorted(self.tools_audit_dir.glob("*.json"))
        ]
        filtered = [audit for audit in audits if audit.agent_id == agent_id]
        if session_id is not None:
            filtered = [audit for audit in filtered if audit.session_id == session_id]
        return filtered

    def create_session(self, session: Session) -> None:
        self.init()
        self.session_path(session.session_id).touch(exist_ok=False)

    def append_event(self, event: SessionEvent) -> None:
        self.init()
        path = self.session_path(event.session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {event.session_id}")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), separators=(",", ":")))
            handle.write("\n")

    def load_events(self, session_id: str) -> list[SessionEvent]:
        path = self.session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        events: list[SessionEvent] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    events.append(SessionEvent.model_validate_json(line))
        return events

    def iter_sessions(self) -> Iterable[str]:
        self.init()
        for path in sorted(self.sessions_dir.glob("*.jsonl")):
            yield path.stem

    def list_agent_session_ids(self, agent_id: str) -> list[str]:
        self.load_agent(agent_id)
        session_ids: list[str] = []
        for session_id in self.iter_sessions():
            try:
                events = self.load_events(session_id)
            except FileNotFoundError:
                continue
            if events and events[0].agent_id == agent_id:
                session_ids.append(session_id)
        return session_ids

    def session_status(self, session_id: str) -> SessionStatus:
        events = self.load_events(session_id)
        if any(event.type == "acceptance" for event in events):
            return SessionStatus.ACCEPTED
        if any(event.type == "error" for event in events):
            return SessionStatus.ERROR
        return SessionStatus.OPEN

    def save_learning_run(self, run: LearningRun) -> None:
        self.init()
        self._write_json(self.learning_run_path(run.run_id), run.model_dump(mode="json"))

    def load_learning_run(self, run_id: str) -> LearningRun:
        path = self.learning_run_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"Learning run not found: {run_id}")
        return LearningRun.model_validate(self._read_json(path))

    def list_learning_runs(self, agent_id: str) -> list[LearningRun]:
        self.load_agent(agent_id)
        runs = [
            LearningRun.model_validate(self._read_json(path))
            for path in sorted(self.learning_runs_dir.glob("*.json"))
        ]
        return [run for run in runs if run.agent_id == agent_id]

    def save_learning_candidate(self, candidate: LearningCandidate) -> None:
        self.init()
        self._write_json(
            self.learning_candidate_path(candidate.candidate_id),
            candidate.model_dump(mode="json"),
        )

    def load_learning_candidate(self, candidate_id: str) -> LearningCandidate:
        path = self.learning_candidate_path(candidate_id)
        if not path.exists():
            raise FileNotFoundError(f"Learning candidate not found: {candidate_id}")
        return LearningCandidate.model_validate(self._read_json(path))

    def list_learning_candidates(
        self,
        agent_id: str,
        state: PromotionState | None = None,
    ) -> list[LearningCandidate]:
        self.load_agent(agent_id)
        candidates = [
            LearningCandidate.model_validate(self._read_json(path))
            for path in sorted(self.learning_candidates_dir.glob("*.json"))
        ]
        filtered = [candidate for candidate in candidates if candidate.agent_id == agent_id]
        if state is not None:
            filtered = [candidate for candidate in filtered if candidate.state == state]
        return filtered

    def save_validation_report(self, report: ValidationReport) -> None:
        self.init()
        self._write_json(self.validation_report_path(report.report_id), report.model_dump(mode="json"))

    def list_validation_reports(self, candidate_id: str) -> list[ValidationReport]:
        reports = [
            ValidationReport.model_validate(self._read_json(path))
            for path in sorted(self.learning_reports_dir.glob("*.json"))
        ]
        return [report for report in reports if report.candidate_id == candidate_id]

    def save_gate_report(self, report: GateDecisionReport) -> None:
        self.init()
        self._write_json(self.gate_report_path(report.report_id), report.model_dump(mode="json"))

    def load_gate_report(self, report_id: str) -> GateDecisionReport:
        path = self.gate_report_path(report_id)
        if not path.exists():
            raise FileNotFoundError(f"Gate report not found: {report_id}")
        return GateDecisionReport.model_validate(self._read_json(path))

    def list_gate_reports(self, candidate_id: str | None = None) -> list[GateDecisionReport]:
        reports = [
            GateDecisionReport.model_validate(self._read_json(path))
            for path in sorted(self.learning_gate_reports_dir.glob("*.json"))
        ]
        if candidate_id is None:
            return reports
        return [report for report in reports if report.candidate_id == candidate_id]

    def save_promotion_policy(self, policy: PromotionPolicy) -> None:
        self.init()
        self._write_json(self.policy_path(policy.agent_id), policy.model_dump(mode="json"))

    def load_promotion_policy(self, agent_id: str) -> PromotionPolicy:
        self.load_agent(agent_id)
        path = self.policy_path(agent_id)
        if not path.exists():
            policy = PromotionPolicy(agent_id=agent_id, mode=PromotionMode.AUTO_LOW_RISK)
            self.save_promotion_policy(policy)
            return policy
        return PromotionPolicy.model_validate(self._read_json(path))

    def save_rollback_record(self, record: RollbackRecord) -> None:
        self.init()
        self._write_json(self.rollback_record_path(record.rollback_id), record.model_dump(mode="json"))

    def list_rollback_records(self, candidate_id: str | None = None) -> list[RollbackRecord]:
        records = [
            RollbackRecord.model_validate(self._read_json(path))
            for path in sorted(self.learning_rollbacks_dir.glob("*.json"))
        ]
        if candidate_id is None:
            return records
        return [record for record in records if record.candidate_id == candidate_id]

    def save_flame_pool_item(self, item: PoolItem) -> None:
        self.init()
        self._write_json(self.flame_pool_path(item.pool_item_id), item.model_dump(mode="json"))

    def list_flame_pool_items(self, agent_id: str | None = None, state: FlamePoolState | None = None) -> list[PoolItem]:
        self.init()
        rows = [
            PoolItem.model_validate(self._read_json(path))
            for path in sorted(self.flame_pool_dir.glob("*.json"))
        ]
        if agent_id is not None:
            rows = [row for row in rows if row.agent_id == agent_id]
        if state is not None:
            rows = [row for row in rows if row.state == state]
        return rows

    def delete_flame_pool_items(self, pool_item_ids: list[str]) -> None:
        self.init()
        for pool_item_id in pool_item_ids:
            path = self.flame_pool_path(pool_item_id)
            if path.exists():
                path.unlink()

    def save_flame_run(self, run: ReflectionBatchRun) -> None:
        self.init()
        self._write_json(self.flame_run_path(run.run_id), run.model_dump(mode="json"))

    def list_flame_runs(self, agent_id: str | None = None) -> list[ReflectionBatchRun]:
        self.init()
        runs = [
            ReflectionBatchRun.model_validate(self._read_json(path))
            for path in sorted(self.flame_runs_dir.glob("*.json"))
        ]
        if agent_id is not None:
            runs = [run for run in runs if run.agent_id == agent_id]
        return runs

    def agent_path(self, agent_id: str) -> Path:
        return self.agents_dir / f"{agent_id}.json"

    def memory_path(self, agent_id: str, memory_id: str) -> Path:
        return self.memory_dir / agent_id / f"{memory_id}.json"

    def session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.jsonl"

    def skill_path(self, skill_id: str) -> Path:
        return self.skills_dir / f"{skill_id}.json"

    def skill_binding_path(self, agent_id: str) -> Path:
        return self.skill_bindings_dir / f"{agent_id}.json"

    def learning_run_path(self, run_id: str) -> Path:
        return self.learning_runs_dir / f"{run_id}.json"

    def learning_candidate_path(self, candidate_id: str) -> Path:
        return self.learning_candidates_dir / f"{candidate_id}.json"

    def validation_report_path(self, report_id: str) -> Path:
        return self.learning_reports_dir / f"{report_id}.json"

    def gate_report_path(self, report_id: str) -> Path:
        return self.learning_gate_reports_dir / f"{report_id}.json"

    def policy_path(self, agent_id: str) -> Path:
        return self.policy_dir / f"{agent_id}.json"

    def rollback_record_path(self, rollback_id: str) -> Path:
        return self.learning_rollbacks_dir / f"{rollback_id}.json"

    def tool_manifest_path(self, tool_id: str) -> Path:
        return self.tools_manifests_dir / f"{tool_id}.json"

    def tool_allowlist_path(self, agent_id: str) -> Path:
        return self.tools_allowlists_dir / f"{agent_id}.json"

    def tool_audit_path(self, audit_id: str) -> Path:
        return self.tools_audit_dir / f"{audit_id}.json"

    def flame_pool_path(self, pool_item_id: str) -> Path:
        return self.flame_pool_dir / f"{pool_item_id}.json"

    def flame_run_path(self, run_id: str) -> Path:
        return self.flame_runs_dir / f"{run_id}.json"

    @staticmethod
    def _read_json(path: Path) -> dict:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
