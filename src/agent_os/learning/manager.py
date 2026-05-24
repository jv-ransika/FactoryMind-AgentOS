from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent_os.protocol import AgentTier, LearningRun, PromotionPolicy, PromotionState
from agent_os.storage import DomainStore
from flame_memory import FlameManager


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearningManager:
    """
    Compatibility facade over FLAME.

    Iteration 19 removes candidate-era APIs; this manager keeps `run`, `list_runs`,
    and promotion policy compatibility while delegating learning execution to FLAME.
    """

    def __init__(
        self,
        store: DomainStore,
        flame: FlameManager,
        usage_tracker: Any | None = None,
    ) -> None:
        self.store = store
        self.flame = flame
        self.usage_tracker = usage_tracker

    def run(self, agent_id: str, session_ids: list[str] | None = None, window_size: int = 50) -> LearningRun:
        _ = session_ids
        _ = window_size
        agent = self.store.load_agent(agent_id)
        if agent.agent_tier != AgentTier.SELF_LEARNING_AGENT:
            raise ValueError("tier_forbids_learning")
        runs = self.flame.trigger(agent_id=agent_id, force=True)
        run = runs[-1] if runs else None
        return LearningRun(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            session_ids=[] if run is None else sorted(set(run.pool_item_ids)),
            candidate_ids=[],
            experience_count=0 if run is None else len(run.pool_item_ids),
            summary="FLAME trigger executed via learning compatibility alias.",
            created_at=utc_now(),
        )

    def list_runs(self, agent_id: str) -> list[LearningRun]:
        flame_runs = self.flame.list_runs(agent_id)
        out: list[LearningRun] = []
        for row in flame_runs:
            out.append(
                LearningRun(
                    run_id=row.run_id,
                    agent_id=row.agent_id,
                    tenant_id=row.tenant_id,
                    session_ids=row.pool_item_ids,
                    candidate_ids=[],
                    experience_count=len(row.pool_item_ids),
                    summary=f"FLAME {row.state.value} ({row.trigger_reason})",
                    created_at=row.created_at,
                )
            )
        return out

    def list_candidates(self, agent_id: str, state: PromotionState | None = None):  # noqa: ANN201
        _ = agent_id
        _ = state
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def validate(self, candidate_id: str):  # noqa: ANN201
        _ = candidate_id
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def evaluate(self, candidate_id: str):  # noqa: ANN201
        _ = candidate_id
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def promote(self, candidate_id: str):  # noqa: ANN201
        _ = candidate_id
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def reject(self, candidate_id: str, reason: str):  # noqa: ANN201
        _ = candidate_id
        _ = reason
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def rollback(self, candidate_id: str, reason: str):  # noqa: ANN201
        _ = candidate_id
        _ = reason
        raise ValueError("learning_candidates_removed_in_v1_2_0")

    def set_policy(self, agent_id: str, policy: PromotionPolicy) -> PromotionPolicy:
        agent = self.store.load_agent(agent_id)
        policy.agent_id = agent_id
        policy.tenant_id = agent.tenant_id
        policy.updated_at = utc_now()
        self.store.save_promotion_policy(policy)
        return policy

    def get_policy(self, agent_id: str) -> PromotionPolicy:
        return self.store.load_promotion_policy(agent_id)
