from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import JSON, Column, MetaData, String, Table, Text, create_engine, delete, select, text

try:  # pragma: no cover - import path varies by environment
    from pgvector.sqlalchemy import Vector
except Exception:  # pragma: no cover - optional dependency path
    Vector = None  # type: ignore[assignment]

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


class PostgresDomainStore:
    def __init__(self, dsn: str, root: Path | str = ".agent-os") -> None:
        self.root = Path(root)
        self.engine = create_engine(self._normalize_dsn(dsn), future=True)
        self.md = MetaData()
        self.records = Table(
            "agent_os_records",
            self.md,
            Column("kind", String(64), nullable=False),
            Column("key", String(255), nullable=False),
            Column("tenant_id", String(255), nullable=True),
            Column("agent_id", String(255), nullable=True),
            Column("session_id", String(255), nullable=True),
            Column("candidate_id", String(255), nullable=True),
            Column("payload", JSON, nullable=False),
            Column("updated_at", String(64), nullable=False),
        )
        self.events = Table(
            "agent_os_session_events",
            self.md,
            Column("session_id", String(255), nullable=False),
            Column("event_id", String(255), nullable=False),
            Column("tenant_id", String(255), nullable=True),
            Column("agent_id", String(255), nullable=False),
            Column("payload", Text, nullable=False),
            Column("created_at", String(64), nullable=False),
        )
        vector_column_type = Vector(1536) if Vector is not None else JSON
        self.memory_vectors = Table(
            "agent_os_memory_vectors",
            self.md,
            Column("memory_id", String(255), primary_key=True),
            Column("tenant_id", String(255), nullable=True),
            Column("agent_id", String(255), nullable=False),
            Column("embedding", vector_column_type, nullable=False),
            Column("updated_at", String(64), nullable=False),
        )

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        if dsn.startswith("postgresql://"):
            return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
        return dsn

    def init(self) -> None:
        self._require_pgvector_python()
        try:
            with self.engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception as exc:
            raise RuntimeError(
                f"pgvector_extension_missing: vector_backend_required: {exc.__class__.__name__}: {exc}"
            ) from exc
        self.md.create_all(self.engine)

    def _require_pgvector_python(self) -> None:
        if Vector is None:
            raise RuntimeError("vector_backend_required: pgvector_python_package_missing")

    def _upsert(self, kind: str, key: str, payload: dict, agent_id: str | None = None, session_id: str | None = None, candidate_id: str | None = None) -> None:
        self.init()
        updated_at = str(payload.get("updated_at", payload.get("created_at", "")))
        tenant_id = str(payload.get("tenant_id", "default"))
        with self.engine.begin() as conn:
            conn.execute(delete(self.records).where(self.records.c.kind == kind, self.records.c.key == key))
            conn.execute(
                self.records.insert().values(
                    kind=kind,
                    key=key,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    candidate_id=candidate_id,
                    payload=payload,
                    updated_at=updated_at,
                )
            )

    def _get(self, kind: str, key: str) -> dict:
        self.init()
        with self.engine.begin() as conn:
            row = conn.execute(select(self.records.c.payload).where(self.records.c.kind == kind, self.records.c.key == key)).first()
        if not row:
            raise FileNotFoundError(f"{kind} not found: {key}")
        return dict(row[0])

    def _list(self, kind: str, agent_id: str | None = None, candidate_id: str | None = None) -> list[dict]:
        self.init()
        stmt = select(self.records.c.payload).where(self.records.c.kind == kind)
        if agent_id is not None:
            stmt = stmt.where(self.records.c.agent_id == agent_id)
        if candidate_id is not None:
            stmt = stmt.where(self.records.c.candidate_id == candidate_id)
        with self.engine.begin() as conn:
            rows = conn.execute(stmt).all()
        return [dict(row[0]) for row in rows]

    def save_agent(self, agent: AgentDefinition) -> None:
        self._upsert("agent", agent.id, agent.model_dump(mode="json"), agent_id=agent.id)

    def load_agent(self, agent_id: str) -> AgentDefinition:
        return AgentDefinition.model_validate(self._get("agent", agent_id))

    def list_agents(self) -> list[AgentDefinition]:
        return [AgentDefinition.model_validate(item) for item in self._list("agent")]

    def save_memory(self, memory: MemoryItem) -> None:
        self._upsert("memory", memory.memory_id, memory.model_dump(mode="json"), agent_id=memory.agent_id)

    def save_memory_vector(self, agent_id: str, memory_id: str, embedding: list[float]) -> None:
        self._require_pgvector_python()
        self.init()
        tenant_id = self.load_agent(agent_id).tenant_id
        with self.engine.begin() as conn:
            conn.execute(delete(self.memory_vectors).where(self.memory_vectors.c.memory_id == memory_id))
            conn.execute(
                self.memory_vectors.insert().values(
                    memory_id=memory_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    embedding=[float(value) for value in embedding],
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )

    def query_memory_vectors(self, agent_id: str, query_embedding: list[float], limit: int = 5) -> list[tuple[str, float]]:
        self._require_pgvector_python()
        self.init()
        if not query_embedding:
            return []
        with self.engine.begin() as conn:
            distance = self.memory_vectors.c.embedding.cosine_distance([float(value) for value in query_embedding])
            stmt = (
                select(self.memory_vectors.c.memory_id, distance.label("distance"))
                .where(self.memory_vectors.c.agent_id == agent_id)
                .order_by(distance.asc())
                .limit(limit)
            )
            rows = conn.execute(stmt).all()
            return [
                (str(row[0]), max(0.0, 1.0 - float(row[1] or 0.0)))
                for row in rows
            ]

    def load_memory(self, agent_id: str, memory_id: str) -> MemoryItem:
        mem = MemoryItem.model_validate(self._get("memory", memory_id))
        if mem.agent_id != agent_id:
            raise FileNotFoundError(f"Memory not found: {memory_id}")
        return mem

    def list_memories(self, agent_id: str) -> list[MemoryItem]:
        return [MemoryItem.model_validate(item) for item in self._list("memory", agent_id=agent_id)]

    def save_skill(self, skill: SkillDefinition) -> None:
        self._upsert("skill", skill.skill_id, skill.model_dump(mode="json"), agent_id=skill.owner_agent_id)

    def load_skill(self, skill_id: str) -> SkillDefinition:
        return SkillDefinition.model_validate(self._get("skill", skill_id))

    def list_skills(self) -> list[SkillDefinition]:
        return [SkillDefinition.model_validate(item) for item in self._list("skill")]

    def bind_skill(self, agent_id: str, skill_id: str) -> None:
        key = f"{agent_id}:{skill_id}"
        self._upsert("skill_binding", key, {"agent_id": agent_id, "skill_id": skill_id}, agent_id=agent_id)

    def list_bound_skill_ids(self, agent_id: str) -> list[str]:
        return [str(item["skill_id"]) for item in self._list("skill_binding", agent_id=agent_id)]

    def save_tool_manifest(self, manifest: ToolManifest) -> None:
        self._upsert("tool_manifest", manifest.tool_id, manifest.model_dump(mode="json"))

    def load_tool_manifest(self, tool_id: str) -> ToolManifest:
        return ToolManifest.model_validate(self._get("tool_manifest", tool_id))

    def list_tool_manifests(self) -> list[ToolManifest]:
        return [ToolManifest.model_validate(item) for item in self._list("tool_manifest")]

    def bind_tool(self, agent_id: str, tool_id: str, allow_write: bool = False) -> None:
        manifest = self.load_tool_manifest(tool_id)
        key = f"{agent_id}:{tool_id}"
        self._upsert(
            "tool_binding",
            key,
            {"agent_id": agent_id, "tool_id": tool_id, "allow_write": bool(allow_write) and manifest.scope == ToolScope.WRITE},
            agent_id=agent_id,
        )

    def list_bound_tools(self, agent_id: str) -> list[dict]:
        return self._list("tool_binding", agent_id=agent_id)

    def save_tool_audit(self, audit: ToolAuditEvent) -> None:
        self._upsert("tool_audit", audit.audit_id, audit.model_dump(mode="json"), agent_id=audit.agent_id, session_id=audit.session_id)

    def list_tool_audits(self, agent_id: str, session_id: str | None = None) -> list[ToolAuditEvent]:
        rows = self._list("tool_audit", agent_id=agent_id)
        audits = [ToolAuditEvent.model_validate(item) for item in rows]
        if session_id is not None:
            audits = [item for item in audits if item.session_id == session_id]
        return audits

    def create_session(self, session: Session) -> None:
        self._upsert("session", session.session_id, session.model_dump(mode="json"), agent_id=session.agent_id, session_id=session.session_id)

    def append_event(self, event: SessionEvent) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                self.events.insert().values(
                    session_id=event.session_id,
                    event_id=event.event_id,
                    tenant_id=event.tenant_id,
                    agent_id=event.agent_id,
                    payload=json.dumps(event.model_dump(mode="json"), separators=(",", ":")),
                    created_at=event.created_at.isoformat(),
                )
            )

    def load_events(self, session_id: str) -> list[SessionEvent]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.events.c.payload).where(self.events.c.session_id == session_id)).all()
        if not rows:
            raise FileNotFoundError(f"Session not found: {session_id}")
        return [SessionEvent.model_validate_json(str(row[0])) for row in rows]

    def iter_sessions(self) -> Iterable[str]:
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.records.c.key).where(self.records.c.kind == "session")).all()
        for row in rows:
            yield str(row[0])

    def list_agent_session_ids(self, agent_id: str) -> list[str]:
        rows = self._list("session", agent_id=agent_id)
        return [str(item["session_id"]) for item in rows]

    def session_status(self, session_id: str) -> SessionStatus:
        events = self.load_events(session_id)
        if any(event.type == "acceptance" for event in events):
            return SessionStatus.ACCEPTED
        if any(event.type == "error" for event in events):
            return SessionStatus.ERROR
        return SessionStatus.OPEN

    def save_learning_run(self, run: LearningRun) -> None:
        self._upsert("learning_run", run.run_id, run.model_dump(mode="json"), agent_id=run.agent_id)

    def load_learning_run(self, run_id: str) -> LearningRun:
        return LearningRun.model_validate(self._get("learning_run", run_id))

    def list_learning_runs(self, agent_id: str) -> list[LearningRun]:
        return [LearningRun.model_validate(item) for item in self._list("learning_run", agent_id=agent_id)]

    def save_learning_candidate(self, candidate: LearningCandidate) -> None:
        self._upsert("learning_candidate", candidate.candidate_id, candidate.model_dump(mode="json"), agent_id=candidate.agent_id, candidate_id=candidate.candidate_id)

    def load_learning_candidate(self, candidate_id: str) -> LearningCandidate:
        return LearningCandidate.model_validate(self._get("learning_candidate", candidate_id))

    def list_learning_candidates(self, agent_id: str, state: PromotionState | None = None) -> list[LearningCandidate]:
        items = [LearningCandidate.model_validate(item) for item in self._list("learning_candidate", agent_id=agent_id)]
        if state is not None:
            items = [item for item in items if item.state == state]
        return items

    def save_validation_report(self, report: ValidationReport) -> None:
        self._upsert("validation_report", report.report_id, report.model_dump(mode="json"), candidate_id=report.candidate_id)

    def list_validation_reports(self, candidate_id: str) -> list[ValidationReport]:
        return [ValidationReport.model_validate(item) for item in self._list("validation_report", candidate_id=candidate_id)]

    def save_gate_report(self, report: GateDecisionReport) -> None:
        self._upsert("gate_report", report.report_id, report.model_dump(mode="json"), agent_id=report.agent_id, candidate_id=report.candidate_id)

    def load_gate_report(self, report_id: str) -> GateDecisionReport:
        return GateDecisionReport.model_validate(self._get("gate_report", report_id))

    def list_gate_reports(self, candidate_id: str | None = None) -> list[GateDecisionReport]:
        return [GateDecisionReport.model_validate(item) for item in self._list("gate_report", candidate_id=candidate_id)]

    def save_promotion_policy(self, policy: PromotionPolicy) -> None:
        self._upsert("policy", policy.agent_id, policy.model_dump(mode="json"), agent_id=policy.agent_id)

    def load_promotion_policy(self, agent_id: str) -> PromotionPolicy:
        try:
            return PromotionPolicy.model_validate(self._get("policy", agent_id))
        except FileNotFoundError:
            policy = PromotionPolicy(agent_id=agent_id, mode=PromotionMode.AUTO_LOW_RISK)
            self.save_promotion_policy(policy)
            return policy

    def save_rollback_record(self, record: RollbackRecord) -> None:
        self._upsert("rollback_record", record.rollback_id, record.model_dump(mode="json"), agent_id=record.agent_id, candidate_id=record.candidate_id)

    def list_rollback_records(self, candidate_id: str | None = None) -> list[RollbackRecord]:
        return [RollbackRecord.model_validate(item) for item in self._list("rollback_record", candidate_id=candidate_id)]

    def save_flame_pool_item(self, item: PoolItem) -> None:
        self._upsert("flame_pool_item", item.pool_item_id, item.model_dump(mode="json"), agent_id=item.agent_id)

    def list_flame_pool_items(self, agent_id: str | None = None, state: FlamePoolState | None = None) -> list[PoolItem]:
        rows = [PoolItem.model_validate(item) for item in self._list("flame_pool_item", agent_id=agent_id)]
        if state is not None:
            rows = [row for row in rows if row.state == state]
        return rows

    def delete_flame_pool_items(self, pool_item_ids: list[str]) -> None:
        self.init()
        if not pool_item_ids:
            return
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.records).where(
                    self.records.c.kind == "flame_pool_item",
                    self.records.c.key.in_(pool_item_ids),
                )
            )

    def save_flame_run(self, run: ReflectionBatchRun) -> None:
        self._upsert("flame_run", run.run_id, run.model_dump(mode="json"), agent_id=run.agent_id)

    def list_flame_runs(self, agent_id: str | None = None) -> list[ReflectionBatchRun]:
        return [ReflectionBatchRun.model_validate(item) for item in self._list("flame_run", agent_id=agent_id)]
