from __future__ import annotations

from typing import Literal

from agent_os.capabilities import ModelCapabilityRegistry
from agent_os.protocol import AgentDefinition, CostRecord, UsageRecord
from agent_os.protocol.models import utc_now

OperationBucket = Literal[
    "main_run",
    "reflection",
    "compaction",
    "summarization",
    "tool_evidence_processing",
    "embedding",
    "flame_extraction",
    "flame_reflection",
]


def record_usage_and_cost(
    *,
    usage_tracker,
    capabilities: ModelCapabilityRegistry | None,
    agent: AgentDefinition,
    operation_bucket: OperationBucket,
    model: str | None,
    request_bytes: int,
    latency_ms: int,
    session_id: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    if usage_tracker is None:
        return
    usage = UsageRecord(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        session_id=session_id,
        operation_bucket=operation_bucket,
        model=model,
        request_bytes=max(0, int(request_bytes)),
        input_tokens=max(0, int(input_tokens)),
        output_tokens=max(0, int(output_tokens)),
        reasoning_tokens=max(0, int(reasoning_tokens)),
        total_tokens=max(0, int(total_tokens)),
        latency_ms=max(0, int(latency_ms)),
        created_at=utc_now(),
    )

    est_cost = None
    status: Literal["computed", "unsupported"] = "unsupported"
    if capabilities is not None and model:
        try:
            capability = capabilities.get(model, verify_provider=False)
            if capability.input_price_per_1m is not None and capability.output_price_per_1m is not None:
                est_cost = (
                    (usage.input_tokens / 1_000_000.0) * float(capability.input_price_per_1m)
                    + (usage.output_tokens / 1_000_000.0) * float(capability.output_price_per_1m)
                )
                status = "computed"
        except Exception:
            status = "unsupported"

    cost = CostRecord(
        usage_id=usage.usage_id,
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        operation_bucket=operation_bucket,
        model=model,
        estimated_cost_usd=est_cost,
        cost_status=status,
        created_at=utc_now(),
    )
    usage_tracker.record(usage=usage, cost=cost)
