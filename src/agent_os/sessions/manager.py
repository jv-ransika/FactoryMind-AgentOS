from __future__ import annotations

from agent_os.protocol import (
    AcceptanceMessage,
    AgentDefinition,
    AgentOutput,
    EventType,
    FeedbackMessage,
    InputMessage,
    Session,
    SessionEvent,
)
from agent_os.runtime import AgentRuntimeAdapter
from agent_os.storage import DomainStore
from agent_os.context import ContextAssembler


class SessionManager:
    def __init__(
        self,
        store: DomainStore,
        runtime: AgentRuntimeAdapter,
        context: ContextAssembler | None = None,
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.context = context

    def init(self, agent_id: str, input: str) -> Session:
        agent = self.store.load_agent(agent_id)
        session = Session(agent_id=agent.id, tenant_id=agent.tenant_id, agent_version=agent.version)
        self.store.create_session(session)
        self.store.append_event(
            SessionEvent(
                session_id=session.session_id,
                agent_id=agent.id,
                tenant_id=agent.tenant_id,
                type=EventType.INPUT,
                payload=InputMessage(input=input).model_dump(mode="json"),
                agent_version=agent.version,
            )
        )
        return session

    def run(self, session_id: str) -> AgentOutput:
        events = self.store.load_events(session_id)
        agent = self._agent_for_events(events)
        input_text = self._latest_input(events)
        context = None
        if self.context is not None:
            budget = None
            cfg = getattr(self.runtime, "config", None)
            if cfg is not None:
                budget = int(getattr(cfg, "default_token_budget", 2500))
            context = self.context.build(agent_id=agent.id, active_input=input_text, events=events, token_budget=budget)
        output = self.runtime.run(agent=agent, events=events, input_text=input_text, context=context)
        self.store.append_event(
            SessionEvent(
                session_id=session_id,
                agent_id=agent.id,
                tenant_id=agent.tenant_id,
                type=EventType.AGENT_OUTPUT,
                payload=output.model_dump(mode="json"),
                agent_version=agent.version,
            )
        )
        return output

    def feedback(self, session_id: str, feedback: str) -> SessionEvent:
        events = self.store.load_events(session_id)
        agent = self._agent_for_events(events)
        event = SessionEvent(
            session_id=session_id,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            type=EventType.FEEDBACK,
            payload=FeedbackMessage(feedback=feedback).model_dump(mode="json"),
            agent_version=agent.version,
        )
        self.store.append_event(event)
        return event

    def accept(self, session_id: str, note: str | None = None) -> SessionEvent:
        events = self.store.load_events(session_id)
        agent = self._agent_for_events(events)
        event = SessionEvent(
            session_id=session_id,
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            type=EventType.ACCEPTANCE,
            payload=AcceptanceMessage(note=note).model_dump(mode="json"),
            agent_version=agent.version,
        )
        self.store.append_event(event)
        return event

    def events(self, session_id: str) -> list[SessionEvent]:
        return self.store.load_events(session_id)

    def _agent_for_events(self, events: list[SessionEvent]) -> AgentDefinition:
        if not events:
            raise ValueError("Session has no events.")
        return self.store.load_agent(events[0].agent_id)

    @staticmethod
    def _latest_input(events: list[SessionEvent]) -> str:
        for event in reversed(events):
            if event.type == EventType.INPUT:
                return str(event.payload.get("input", ""))
        return ""
