from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class LearningMode(StrEnum):
    OFF = "off"
    COLLECT_ONLY = "collect_only"
    SUGGEST = "suggest"
    AUTO_LOW_RISK = "auto_low_risk"
    MANUAL_HIGH_RISK = "manual_high_risk"


class OutputType(StrEnum):
    QUESTION = "question"
    FINAL = "final"
    ERROR = "error"


class EventType(StrEnum):
    INPUT = "input"
    AGENT_OUTPUT = "agent_output"
    FEEDBACK = "feedback"
    ACCEPTANCE = "acceptance"
    TOOL_CALL = "tool_call"
    ERROR = "error"


class SessionStatus(StrEnum):
    OPEN = "open"
    ACCEPTED = "accepted"
    ERROR = "error"


class MemoryScope(StrEnum):
    USER = "user"
    AGENT = "agent"
    COMPANY = "company"
    GLOBAL = "global"


class MemoryType(StrEnum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    FEEDBACK = "feedback"
    SAFETY = "safety"
    ARTIFACT = "artifact"


class ResourceStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"
    REJECTED = "rejected"


class Confidence(BaseModel):
    level: Literal["low", "medium", "high"] = "low"
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    basis: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    requires_human_check: bool = True


class AgentOutput(BaseModel):
    type: OutputType
    content: str
    confidence: Confidence = Field(default_factory=Confidence)


class AgentDefinition(BaseModel):
    id: str
    goal: str
    model: str
    tenant_id: str = "default"
    version: str = "0.1.0-beta.3"
    learning_mode: LearningMode = LearningMode.COLLECT_ONLY
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: new_id("ses"))
    agent_id: str
    tenant_id: str = "default"
    status: SessionStatus = SessionStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    agent_version: str = "0.1.0-beta.3"


class SessionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    session_id: str
    agent_id: str
    tenant_id: str = "default"
    type: EventType
    created_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
    agent_version: str = "0.1.0-beta.3"


class InputMessage(BaseModel):
    input: str


class FeedbackMessage(BaseModel):
    feedback: str


class AcceptanceMessage(BaseModel):
    accepted: bool = True
    note: str | None = None


class MemoryItem(BaseModel):
    memory_id: str = Field(default_factory=lambda: new_id("mem"))
    agent_id: str
    tenant_id: str = "default"
    scope: MemoryScope = MemoryScope.AGENT
    memory_type: MemoryType = MemoryType.SEMANTIC
    content: str
    summary: str = ""
    status: ResourceStatus = ResourceStatus.ACTIVE
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SkillDefinition(BaseModel):
    skill_id: str = Field(default_factory=lambda: new_id("skl"))
    tenant_id: str = "default"
    owner_agent_id: str | None = None
    name: str
    description: str
    activation_keywords: list[str] = Field(default_factory=list)
    procedure: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    status: ResourceStatus = ResourceStatus.ACTIVE
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RetrievalResult(BaseModel):
    query: str
    matched_terms: list[str] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0)


class RetrievedMemory(BaseModel):
    item: MemoryItem
    retrieval: RetrievalResult


class RetrievedSkill(BaseModel):
    skill: SkillDefinition
    retrieval: RetrievalResult


class ContextPacket(BaseModel):
    agent_id: str
    active_input: str
    latest_feedback: str | None = None
    selected_memories: list[RetrievedMemory] = Field(default_factory=list)
    selected_skills: list[RetrievedSkill] = Field(default_factory=list)
    tool_evidence: list[dict[str, Any]] = Field(default_factory=list)
    token_budget: int | None = None
    estimated_tokens: int | None = None
    truncated: bool = False


class RuntimeConfig(BaseModel):
    mode: Literal["local", "openai"] = "local"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_timeout_ms: int = Field(default=20000, ge=1)
    openai_max_retries: int = Field(default=1, ge=0)
    default_token_budget: int = Field(default=2500, ge=100)


class CandidateType(StrEnum):
    MEMORY = "memory"
    SKILL = "skill"


class RefinementOp(StrEnum):
    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"
    COMBINE = "combine"


class PromotionState(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    EVALUATING = "evaluating"
    AWAITING_APPROVAL = "awaiting_approval"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class PromotionMode(StrEnum):
    SUGGEST_ONLY = "suggest_only"
    AUTO_LOW_RISK = "auto_low_risk"
    MANUAL_ONLY = "manual_only"


class ExperienceRecord(BaseModel):
    experience_id: str = Field(default_factory=lambda: new_id("exp"))
    agent_id: str
    session_id: str
    accepted: bool
    input_text: str
    output_text: str = ""
    feedback_texts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class LearningCandidate(BaseModel):
    candidate_id: str = Field(default_factory=lambda: new_id("cand"))
    agent_id: str
    tenant_id: str = "default"
    candidate_type: CandidateType
    operation: RefinementOp
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    source_session_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"] = "low"
    state: PromotionState = PromotionState.CREATED
    rationale: str = ""
    last_gate_report_id: str | None = None
    last_gate_decision: Literal["pass", "fail"] | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ValidationReport(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("vrp"))
    candidate_id: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    quality_delta: float = 0.0
    safety_flags: list[str] = Field(default_factory=list)
    regression_flags: list[str] = Field(default_factory=list)
    decision: Literal["pass", "fail"] = "fail"
    explanation: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class LearningRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("lrn"))
    agent_id: str
    tenant_id: str = "default"
    session_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    experience_count: int = 0
    summary: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class PromotionPolicy(BaseModel):
    agent_id: str
    tenant_id: str = "default"
    mode: PromotionMode = PromotionMode.AUTO_LOW_RISK
    max_safety_failures: int = Field(default=0, ge=0)
    max_regression_warnings: int = Field(default=1, ge=0)
    min_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    min_quality_delta: float = Field(default=0.02)
    updated_at: datetime = Field(default_factory=utc_now)


class GateDecisionReport(BaseModel):
    report_id: str = Field(default_factory=lambda: new_id("gdr"))
    candidate_id: str
    agent_id: str
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    safety_failures: int = 0
    regression_warnings: int = 0
    candidate_confidence: float = 0.0
    quality_delta: float = 0.0
    baseline_score: float = 0.0
    candidate_score: float = 0.0
    replay_samples: int = 0
    threshold_snapshot: dict[str, Any] = Field(default_factory=dict)
    decision: Literal["pass", "fail"] = "fail"
    explanation: str = ""
    rollback_ready: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class RollbackRecord(BaseModel):
    rollback_id: str = Field(default_factory=lambda: new_id("rbk"))
    candidate_id: str
    agent_id: str
    tenant_id: str = "default"
    actions: list[dict[str, Any]] = Field(default_factory=list)
    applied: bool = False
    reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    applied_at: datetime | None = None


class ToolScope(StrEnum):
    READ = "read"
    WRITE = "write"


class ToolCallStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"
    INVALID = "invalid"


class ToolManifest(BaseModel):
    tool_id: str = Field(default_factory=lambda: new_id("tool"))
    name: str
    tenant_id: str = "default"
    scope: ToolScope = ToolScope.READ
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = Field(default=2000, ge=1)
    max_input_bytes: int = Field(default=8192, ge=1)
    max_output_bytes: int = Field(default=32768, ge=1)
    enabled: bool = True
    version: str = "1.0.0"
    mcp_server: str | None = None
    mcp_tool_name: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ToolCallRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: new_id("tcr"))
    session_id: str | None = None
    agent_id: str
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ToolCallResult(BaseModel):
    request_id: str
    status: ToolCallStatus
    output: dict[str, Any] | None = None
    duration_ms: int = 0
    error_code: str | None = None
    error_message: str | None = None
    sanitized_output: dict[str, Any] | None = None


class ToolAuditEvent(BaseModel):
    audit_id: str = Field(default_factory=lambda: new_id("tae"))
    session_id: str | None = None
    agent_id: str
    tenant_id: str = "default"
    tool_id: str
    request_hash: str
    status: ToolCallStatus
    duration_ms: int
    sanitization_applied: bool = False
    error_code: str | None = None
    summary_evidence: dict[str, Any] = Field(default_factory=dict)
    mcp: dict[str, Any] | None = None
    actor_sub: str | None = None
    actor_roles: list[str] = Field(default_factory=list)
    auth_method: str = "none"
    prev_hash: str | None = None
    entry_hash: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class McpServerConfig(BaseModel):
    name: str
    transport: Literal["http"] = "http"
    endpoint: str
    auth_env_var: str | None = None
    timeout_ms: int = Field(default=2000, ge=1)
    enabled: bool = True


class AuthContext(BaseModel):
    sub: str
    tenant_id: str
    roles: list[str]


class AuthConfig(BaseModel):
    issuer: str
    audience: str
    jwks_url: str | None = None
    public_key_path: str | None = None
    clock_skew_seconds: int = Field(default=30, ge=0)


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"
    OPS = "ops"
