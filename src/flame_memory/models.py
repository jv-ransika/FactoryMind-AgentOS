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
