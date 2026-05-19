from __future__ import annotations

from agent_os.protocol import (
    AcceptanceMessage,
    AgentDefinition,
    AgentOutput,
    ContextPacket,
    EventType,
    FeedbackMessage,
    InputMessage,
    OutputType,
    RuntimeConfig,
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
        self.on_accept = None

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
        context = self._build_context(agent=agent, events=events, input_text=input_text)
        output = self.runtime.run(agent=agent, events=events, input_text=input_text, context=context)
        output = self._repair_low_confidence_output(
            agent=agent,
            events=events,
            input_text=input_text,
            context=context,
            output=output,
        )
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
        if callable(self.on_accept):
            self.on_accept(session_id=session_id, agent_id=agent.id)
        return event

    def events(self, session_id: str) -> list[SessionEvent]:
        return self.store.load_events(session_id)

    def _build_context(self, agent: AgentDefinition, events: list[SessionEvent], input_text: str) -> ContextPacket | None:
        if self.context is None:
            return None
        budget = None
        cfg = self._runtime_config()
        if cfg is not None:
            budget = int(getattr(cfg, "default_token_budget", 2500))
        return self.context.build(
            agent_id=agent.id,
            active_input=input_text,
            events=events,
            token_budget=budget,
            agent_tier=agent.agent_tier,
        )

    def _repair_low_confidence_output(
        self,
        agent: AgentDefinition,
        events: list[SessionEvent],
        input_text: str,
        context: ContextPacket | None,
        output: AgentOutput,
    ) -> AgentOutput:
        cfg = self._runtime_config()
        if cfg is None:
            cfg = RuntimeConfig()
        if not bool(getattr(cfg, "confidence_repair_enabled", True)):
            return output
        max_attempts = int(getattr(cfg, "confidence_repair_max_attempts", 1))
        if max_attempts <= 0:
            return output
        threshold = float(getattr(cfg, "confidence_threshold", 0.60))

        initial_output = output
        attempts = 0
        while (
            attempts < max_attempts
            and output.type == OutputType.FINAL
            and float(output.confidence.score) < threshold
        ):
            attempts += 1
            repair_input = self._confidence_repair_input(input_text=input_text, output=output, threshold=threshold)
            repair_context = self._build_context(agent=agent, events=events, input_text=repair_input) or context
            output = self.runtime.run(agent=agent, events=events, input_text=repair_input, context=repair_context)

        if attempts:
            output.runtime_metadata = {
                **output.runtime_metadata,
                "confidence_repair_attempted": True,
                "confidence_repair_attempts": attempts,
                "initial_confidence_score": initial_output.confidence.score,
                "initial_confidence_basis": list(initial_output.confidence.basis),
            }
        return output

    @staticmethod
    def _confidence_repair_input(input_text: str, output: AgentOutput, threshold: float) -> str:
        return (
            f"{input_text}\n\n"
            "Your previous final answer had low confidence "
            f"({output.confidence.score:.2f}, below the threshold {threshold:.2f}). "
            "If you do not have enough information, ask a clarifying question. "
            "Do not guess. If you can improve the answer using available context, "
            "return a better answer with updated confidence.\n\n"
            f"Previous answer: {output.content}\n"
            f"Confidence basis: {', '.join(output.confidence.basis) if output.confidence.basis else 'none'}\n"
            f"Uncertainties: {', '.join(output.confidence.uncertainties) if output.confidence.uncertainties else 'none'}"
        )

    def _runtime_config(self) -> RuntimeConfig | None:
        cfg = getattr(self.runtime, "config", None)
        return cfg if isinstance(cfg, RuntimeConfig) else cfg

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
