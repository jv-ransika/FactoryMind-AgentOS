from __future__ import annotations

from abc import ABC, abstractmethod

from agent_os.protocol import AgentDefinition, AgentOutput, ContextPacket, SessionEvent


class AgentRuntimeAdapter(ABC):
    @abstractmethod
    def run(
        self,
        agent: AgentDefinition,
        events: list[SessionEvent],
        input_text: str,
        context: ContextPacket | None = None,
    ) -> AgentOutput:
        """Run or resume a session and return a typed agent output."""
