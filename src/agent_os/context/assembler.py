from __future__ import annotations

from agent_os.memory import MemoryManager
from agent_os.protocol import ContextPacket, EventType, SessionEvent
from agent_os.skills import SkillManager


class ContextAssembler:
    def __init__(self, memory: MemoryManager, skills: SkillManager) -> None:
        self.memory = memory
        self.skills = skills

    def build(
        self,
        agent_id: str,
        active_input: str,
        events: list[SessionEvent] | None = None,
        token_budget: int | None = None,
    ) -> ContextPacket:
        latest_feedback = self._latest_feedback(events or [])
        retrieval_query = " ".join(
            part for part in [active_input, latest_feedback or ""] if part.strip()
        )
        packet = ContextPacket(
            agent_id=agent_id,
            active_input=active_input,
            latest_feedback=latest_feedback,
            selected_memories=self.memory.retrieve(agent_id, retrieval_query),
            selected_skills=self.skills.retrieve(agent_id, retrieval_query),
            tool_evidence=self._tool_evidence(events or []),
            token_budget=token_budget,
            estimated_tokens=None,
            truncated=False,
        )
        return self._apply_budget(packet)

    @staticmethod
    def _latest_feedback(events: list[SessionEvent]) -> str | None:
        for event in reversed(events):
            if event.type == EventType.FEEDBACK:
                feedback = event.payload.get("feedback")
                return str(feedback) if feedback else None
        return None

    @staticmethod
    def _tool_evidence(events: list[SessionEvent]) -> list[dict]:
        evidence: list[dict] = []
        for event in events:
            if event.type != EventType.TOOL_CALL:
                continue
            summary = event.payload.get("summary_evidence")
            if isinstance(summary, dict):
                evidence.append(summary)
        return evidence[-5:]

    def _apply_budget(self, packet: ContextPacket) -> ContextPacket:
        budget = packet.token_budget
        est = self._estimate_tokens(packet)
        packet.estimated_tokens = est
        if budget is None or est <= budget:
            return packet

        # precedence: keep input + latest feedback, then skills, memories, tool evidence.
        packet.truncated = True
        while packet.tool_evidence and self._estimate_tokens(packet) > budget:
            packet.tool_evidence = packet.tool_evidence[:-1]
        while packet.selected_memories and self._estimate_tokens(packet) > budget:
            packet.selected_memories = packet.selected_memories[:-1]
        while packet.selected_skills and self._estimate_tokens(packet) > budget:
            packet.selected_skills = packet.selected_skills[:-1]
        packet.estimated_tokens = self._estimate_tokens(packet)
        return packet

    @staticmethod
    def _estimate_tokens(packet: ContextPacket) -> int:
        parts: list[str] = [packet.active_input]
        if packet.latest_feedback:
            parts.append(packet.latest_feedback)
        parts.extend(item.skill.description for item in packet.selected_skills)
        parts.extend(item.item.summary or item.item.content for item in packet.selected_memories)
        parts.extend(str(item) for item in packet.tool_evidence)
        text = " ".join(part for part in parts if part)
        words = len(text.split())
        return max(1, int(words * 1.3) + 10)
