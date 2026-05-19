from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field
from pydantic import model_validator


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


class AgentTier(StrEnum):
    BASIC_AGENT = "basic_agent"
    SELF_LEARNING_AGENT = "self_learning_agent"


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
    content_json: dict[str, Any] | None = None
    confidence: Confidence = Field(default_factory=Confidence)
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_content_json(self) -> "AgentOutput":
        if self.content_json is not None and self.type != OutputType.FINAL:
            raise ValueError("content_json is only allowed for final outputs.")
        return self


class AgentDefinition(BaseModel):
    id: str
    goal: str
    model: str
    tenant_id: str = "default"
    version: str = "2.0.0"
    agent_tier: AgentTier = AgentTier.BASIC_AGENT
    learning_mode: LearningMode = LearningMode.COLLECT_ONLY
    tools: list[str] = Field(default_factory=list)
    output_mode: Literal["text", "json_schema"] = "text"
    output_schema: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_output_mode(self) -> "AgentDefinition":
        if self.output_mode == "json_schema":
            if not isinstance(self.output_schema, dict) or not self.output_schema:
                raise ValueError("output_schema is required when output_mode=json_schema.")
        return self


class Session(BaseModel):
    session_id: str = Field(default_factory=lambda: new_id("ses"))
    agent_id: str
    tenant_id: str = "default"
    status: SessionStatus = SessionStatus.OPEN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    agent_version: str = "2.0.0"


class SessionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    session_id: str
    agent_id: str
    tenant_id: str = "default"
    type: EventType
    created_at: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
    agent_version: str = "2.0.0"


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
    metadata: dict[str, Any] = Field(default_factory=dict)
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
    score_source: str = "keyword_overlap"


class RetrievedMemory(BaseModel):
    item: MemoryItem
    retrieval: RetrievalResult


class MemoryWriteRequest(BaseModel):
    agent_id: str
    content: str
    summary: str = ""
    scope: MemoryScope = MemoryScope.AGENT
    memory_type: MemoryType = MemoryType.SEMANTIC
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: ResourceStatus = ResourceStatus.ACTIVE


class MemoryWriteResult(BaseModel):
    memory: MemoryItem


class MemoryRetrievalRequest(BaseModel):
    agent_id: str
    query: str
    limit: int = Field(default=5, ge=1)


class MemoryRetrievalResult(BaseModel):
    memories: list[RetrievedMemory] = Field(default_factory=list)


class MemoryEvent(BaseModel):
    event_type: str
    agent_id: str | None = None
    tenant_id: str = "default"
    session_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class RetrievedSkill(BaseModel):
    skill: SkillDefinition
    retrieval: RetrievalResult


class ContextPacket(BaseModel):
    agent_id: str
    active_input: str
    latest_feedback: str | None = None
    selected_memories: list[RetrievedMemory] = Field(default_factory=list)
    tool_evidence: list[dict[str, Any]] = Field(default_factory=list)
    token_budget: int | None = None
    estimated_tokens: int | None = None
    truncated: bool = False
    truncation_notes: list[str] = Field(default_factory=list)


class RuntimeConfig(BaseModel):
    mode: Literal["local", "openai"] = "local"
    runtime_engine: Literal["legacy_openai", "openai_agents_sdk"] = "openai_agents_sdk"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_timeout_ms: int = Field(default=20000, ge=1)
    openai_max_retries: int = Field(default=1, ge=0)
    default_token_budget: int = Field(default=2500, ge=100)
    reserve_output_tokens: int = Field(default=2048, ge=1)
    context_safety_margin_tokens: int = Field(default=512, ge=0)
    flame_pool_size_trigger: int = Field(default=12, ge=1)
    flame_time_trigger_hours: int = Field(default=24, ge=1)
    flame_extraction_model: str = "gpt-4.1-mini"
    flame_reflection_model: str = "gpt-4.1-mini"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    memory_vector_top_k: int = Field(default=5, ge=1)
    confidence_repair_enabled: bool = True
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    confidence_repair_max_attempts: int = Field(default=1, ge=0)


class RuntimeMetadata(BaseModel):
    runtime_engine: Literal["openai_agents_sdk", "legacy_openai"]
    sdk_run_id: str | None = None
    sdk_session_backend: str | None = None
    compaction_applied: bool = False


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


class ExtractedType(StrEnum):
    EXPERIENCE = "experience"
    LEARNING_POINT = "learning_point"


class FlamePoolState(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"


class FlameRunState(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SessionRecord(BaseModel):
    session_id: str
    agent_id: str
    tenant_id: str = "default"
    initial_input: str
    exchange_log: list[dict[str, str]] = Field(default_factory=list)
    final_output: str = ""
    human_feedback_present: bool = False
    timestamp: datetime = Field(default_factory=utc_now)


class ExtractedItem(BaseModel):
    extracted_id: str = Field(default_factory=lambda: new_id("ext"))
    session_id: str
    agent_id: str
    tenant_id: str = "default"
    extracted_at: datetime = Field(default_factory=utc_now)
    type: ExtractedType
    content: str
    human_feedback_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    source_feedback_snippets: list[str] = Field(default_factory=list)


class PoolItem(BaseModel):
    pool_item_id: str = Field(default_factory=lambda: new_id("fpl"))
    agent_id: str
    tenant_id: str = "default"
    session_id: str
    extracted_type: ExtractedType
    content: str
    human_feedback_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    source_feedback_snippets: list[str] = Field(default_factory=list)
    embedding: list[float] = Field(default_factory=list)
    state: FlamePoolState = FlamePoolState.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReflectionItem(BaseModel):
    reflection_id: str = Field(default_factory=lambda: new_id("rfl"))
    agent_id: str
    tenant_id: str = "default"
    content: str
    derived_from: list[str] = Field(default_factory=list)
    human_feedback_weighted: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)


class ReflectionBatchRun(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("flr"))
    agent_id: str
    tenant_id: str = "default"
    trigger_reason: Literal["size", "time", "force"]
    state: FlameRunState = FlameRunState.SKIPPED
    pool_item_ids: list[str] = Field(default_factory=list)
    reflection_ids: list[str] = Field(default_factory=list)
    cluster_count: int = 0
    error: str | None = None
    extraction_prompt_version: str | None = None
    extraction_prompt_hash: str | None = None
    reflection_prompt_version: str | None = None
    reflection_prompt_hash: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class FlameStatus(BaseModel):
    agent_id: str
    tenant_id: str = "default"
    pending_pool_items: int = 0
    oldest_pending_age_seconds: int | None = None
    last_run_state: FlameRunState | None = None
    last_run_at: datetime | None = None


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


class ModelCapability(BaseModel):
    model_id: str
    context_window: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    input_price_per_1m: float | None = Field(default=None, ge=0.0)
    output_price_per_1m: float | None = Field(default=None, ge=0.0)
    cached_input_price_per_1m: float | None = Field(default=None, ge=0.0)
    source: Literal["local_catalog", "provider_verified"] = "local_catalog"
    catalog_version: str = "2026-05-02"
    updated_at: datetime = Field(default_factory=utc_now)


class UsageRecord(BaseModel):
    usage_id: str = Field(default_factory=lambda: new_id("usg"))
    agent_id: str
    tenant_id: str = "default"
    session_id: str | None = None
    operation_bucket: Literal[
        "main_run",
        "reflection",
        "compaction",
        "summarization",
        "tool_evidence_processing",
        "embedding",
        "flame_extraction",
        "flame_reflection",
    ]
    model: str | None = None
    request_bytes: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class CostRecord(BaseModel):
    cost_id: str = Field(default_factory=lambda: new_id("cst"))
    usage_id: str
    agent_id: str
    tenant_id: str = "default"
    operation_bucket: Literal[
        "main_run",
        "reflection",
        "compaction",
        "summarization",
        "tool_evidence_processing",
        "embedding",
        "flame_extraction",
        "flame_reflection",
    ]
    model: str | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    cost_status: Literal["computed", "unsupported"] = "unsupported"
    created_at: datetime = Field(default_factory=utc_now)


class AgentStatus(BaseModel):
    agent_id: str
    tenant_id: str = "default"
    model: str
    tier: AgentTier
    learning_enabled: bool
    open_sessions: int = 0
    accepted_sessions: int = 0
    queued_learning_jobs: int = 0
    failed_jobs: int = 0
    promoted_memories: int = 0
    rejected_candidates: int = 0
    rolled_back_candidates: int = 0
    updated_at: datetime = Field(default_factory=utc_now)


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
