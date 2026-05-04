from __future__ import annotations

from datetime import datetime
from typing import Any

from agent_os.protocol import AgentStatus, AgentTier


class MonitorManager:
    def __init__(self, agent_os: Any) -> None:
        self.agent_os = agent_os

    def status(self, agent_id: str) -> AgentStatus:
        agent = self.agent_os.get_agent(agent_id)
        session_ids = self.agent_os.store.list_agent_session_ids(agent_id)
        open_sessions = 0
        accepted_sessions = 0
        for session_id in session_ids:
            status = self.agent_os.store.session_status(session_id)
            if status == "accepted":
                accepted_sessions += 1
            elif status == "open":
                open_sessions += 1

        memories = self.agent_os.memory.list(agent_id)
        promoted = len([m for m in memories if m.metadata.get("created_by") == "flame_reflection"])
        rejected = 0
        rolled_back = 0

        failed_jobs = self.agent_os.metrics.read().get("jobs_failed", 0)
        queued_learning_jobs = self.agent_os.metrics.read().get("queue_depth", 0)
        return AgentStatus(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            model=agent.model,
            tier=agent.agent_tier,
            learning_enabled=(agent.agent_tier == AgentTier.SELF_LEARNING_AGENT),
            open_sessions=open_sessions,
            accepted_sessions=accepted_sessions,
            queued_learning_jobs=int(queued_learning_jobs),
            failed_jobs=int(failed_jobs),
            promoted_memories=promoted,
            rejected_candidates=rejected,
            rolled_back_candidates=rolled_back,
        )

    def usage(self, agent_id: str, start: datetime | None = None, end: datetime | None = None):
        return self.agent_os.usage.list_usage(agent_id=agent_id, start=start, end=end)

    def costs(self, agent_id: str, start: datetime | None = None, end: datetime | None = None):
        return self.agent_os.usage.list_costs(agent_id=agent_id, start=start, end=end)
