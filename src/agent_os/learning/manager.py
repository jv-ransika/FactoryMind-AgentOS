from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agent_os.memory import MemoryManager
from agent_os.protocol import (
    CandidateType,
    EventType,
    ExperienceRecord,
    GateDecisionReport,
    LearningCandidate,
    LearningRun,
    MemoryItem,
    MemoryType,
    PromotionMode,
    PromotionPolicy,
    PromotionState,
    RefinementOp,
    ResourceStatus,
    RollbackRecord,
    SkillDefinition,
    ValidationReport,
)
from agent_os.retrieval import keywords
from agent_os.skills import SkillManager
from agent_os.storage import DomainStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LearningManager:
    def __init__(
        self,
        store: DomainStore,
        memory: MemoryManager,
        skills: SkillManager,
    ) -> None:
        self.store = store
        self.memory = memory
        self.skills = skills

    def set_policy(self, agent_id: str, policy: PromotionPolicy) -> PromotionPolicy:
        agent = self.store.load_agent(agent_id)
        policy.agent_id = agent_id
        policy.tenant_id = agent.tenant_id
        policy.updated_at = utc_now()
        self.store.save_promotion_policy(policy)
        return policy

    def get_policy(self, agent_id: str) -> PromotionPolicy:
        return self.store.load_promotion_policy(agent_id)

    def run(self, agent_id: str, session_ids: list[str] | None = None, window_size: int = 50) -> LearningRun:
        agent = self.store.load_agent(agent_id)
        policy = self.get_policy(agent_id)
        selected_session_ids = session_ids or self.store.list_agent_session_ids(agent_id)[-window_size:]
        experiences = self._collect_experiences(agent_id, selected_session_ids)
        candidates = self._build_candidates(agent_id, experiences)
        for candidate in candidates:
            self.store.save_learning_candidate(candidate)
            gate = self.evaluate(candidate.candidate_id)
            if gate.decision == "pass":
                candidate = self.store.load_learning_candidate(candidate.candidate_id)
                if policy.mode == PromotionMode.AUTO_LOW_RISK and candidate.risk_level == "low":
                    self.promote(candidate.candidate_id)
                else:
                    candidate.state = PromotionState.AWAITING_APPROVAL
                    candidate.updated_at = utc_now()
                    self.store.save_learning_candidate(candidate)

        run = LearningRun(
            agent_id=agent_id,
            tenant_id=agent.tenant_id,
            session_ids=[experience.session_id for experience in experiences],
            candidate_ids=[candidate.candidate_id for candidate in candidates],
            experience_count=len(experiences),
            summary=f"Processed {len(experiences)} accepted session(s), generated {len(candidates)} candidate(s).",
        )
        self.store.save_learning_run(run)
        return run

    def list_runs(self, agent_id: str) -> list[LearningRun]:
        return self.store.list_learning_runs(agent_id)

    def list_candidates(
        self,
        agent_id: str,
        state: PromotionState | None = None,
    ) -> list[LearningCandidate]:
        return self.store.list_learning_candidates(agent_id, state=state)

    def evaluate(self, candidate_id: str) -> GateDecisionReport:
        candidate = self.store.load_learning_candidate(candidate_id)
        candidate.state = PromotionState.VALIDATING
        candidate.updated_at = utc_now()
        self.store.save_learning_candidate(candidate)

        policy = self.get_policy(candidate.agent_id)
        checks_passed: list[str] = []
        checks_failed: list[str] = []
        safety_flags: list[str] = []
        regression_flags: list[str] = []

        if candidate.candidate_type == CandidateType.MEMORY:
            required = {"content", "summary", "tags", "memory_type"}
        else:
            required = {"name", "description", "activation_keywords", "procedure", "constraints"}
        missing = [field for field in required if field not in candidate.payload]
        if missing:
            checks_failed.append(f"missing_required_payload:{','.join(sorted(missing))}")
        else:
            checks_passed.append("payload_schema")

        payload_text = " ".join(
            [str(value) for value in candidate.payload.values()] + [str(key) for key in candidate.payload.keys()]
        ).lower()
        blocked_markers = ["api_key", "secret", "token", "password", "policy", "permission", "tool_scope"]
        for marker in blocked_markers:
            if marker in payload_text:
                safety_flags.append(f"sensitive_or_forbidden_marker:{marker}")
        safety_failures = len(safety_flags)
        if safety_failures <= policy.max_safety_failures:
            checks_passed.append("safety")
        else:
            checks_failed.append("safety")

        baseline_score, candidate_score, replay_samples, activation_error = self._replay_scores(candidate)
        quality_delta = candidate_score - baseline_score
        if activation_error > 0.10:
            regression_flags.append("activation_error_rate_high")
        if quality_delta < policy.min_quality_delta:
            regression_flags.append("quality_delta_below_threshold")
            checks_failed.append("quality_delta")
        regression_warnings = len(regression_flags)
        if regression_warnings <= policy.max_regression_warnings:
            checks_passed.append("regression")
        else:
            checks_failed.append("regression")

        if candidate.confidence >= policy.min_confidence:
            checks_passed.append("confidence")
        else:
            checks_failed.append("confidence")

        decision = "pass" if not checks_failed else "fail"
        explanation = (
            "Candidate passed replay-backed promotion gates."
            if decision == "pass"
            else "Candidate failed promotion gates."
        )
        report = GateDecisionReport(
            candidate_id=candidate.candidate_id,
            agent_id=candidate.agent_id,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            safety_failures=safety_failures,
            regression_warnings=regression_warnings,
            candidate_confidence=candidate.confidence,
            quality_delta=quality_delta,
            baseline_score=baseline_score,
            candidate_score=candidate_score,
            replay_samples=replay_samples,
            threshold_snapshot={
                "mode": policy.mode.value,
                "max_safety_failures": policy.max_safety_failures,
                "max_regression_warnings": policy.max_regression_warnings,
                "min_confidence": policy.min_confidence,
                "min_quality_delta": policy.min_quality_delta,
            },
            decision=decision,
            explanation=explanation,
            rollback_ready=(decision == "pass"),
        )
        self.store.save_gate_report(report)

        # Compatibility report for existing validation consumers.
        validation = ValidationReport(
            candidate_id=candidate.candidate_id,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            quality_delta=quality_delta,
            safety_flags=safety_flags,
            regression_flags=regression_flags,
            decision=decision,
            explanation=explanation,
        )
        self.store.save_validation_report(validation)

        candidate.last_gate_report_id = report.report_id
        candidate.last_gate_decision = report.decision
        candidate.state = PromotionState.AWAITING_APPROVAL if decision == "pass" else PromotionState.REJECTED
        candidate.updated_at = utc_now()
        self.store.save_learning_candidate(candidate)
        return report

    def validate(self, candidate_id: str) -> ValidationReport:
        self.evaluate(candidate_id)
        reports = self.store.list_validation_reports(candidate_id)
        if not reports:
            raise ValueError("Validation report was not generated.")
        return reports[-1]

    def promote(self, candidate_id: str) -> LearningCandidate:
        candidate = self.store.load_learning_candidate(candidate_id)
        if candidate.last_gate_decision != "pass":
            raise ValueError("Candidate gate decision is not pass; promote denied.")

        if candidate.state not in {PromotionState.AWAITING_APPROVAL, PromotionState.PROMOTED}:
            raise ValueError("Candidate is not eligible for promotion.")
        if candidate.state == PromotionState.PROMOTED:
            return candidate

        actions = self._apply_candidate_and_collect_actions(candidate)
        rollback = RollbackRecord(
            candidate_id=candidate.candidate_id,
            agent_id=candidate.agent_id,
            tenant_id=candidate.tenant_id,
            actions=actions,
            applied=False,
        )
        self.store.save_rollback_record(rollback)

        candidate.state = PromotionState.PROMOTED
        candidate.updated_at = utc_now()
        self.store.save_learning_candidate(candidate)
        return candidate

    def rollback(self, candidate_id: str, reason: str) -> RollbackRecord:
        if not reason.strip():
            raise ValueError("Rollback reason is required.")
        candidate = self.store.load_learning_candidate(candidate_id)
        records = self.store.list_rollback_records(candidate_id=candidate_id)
        if not records:
            raise ValueError("No rollback record exists for this candidate.")
        record = sorted(records, key=lambda item: item.created_at)[-1]
        if record.applied:
            return record

        self._revert_actions(record.actions)
        record.applied = True
        record.reason = reason.strip()
        record.applied_at = utc_now()
        self.store.save_rollback_record(record)

        candidate.state = PromotionState.ROLLED_BACK
        candidate.updated_at = utc_now()
        self.store.save_learning_candidate(candidate)
        return record

    def reject(self, candidate_id: str, reason: str) -> LearningCandidate:
        if not reason.strip():
            raise ValueError("Reject reason is required.")
        candidate = self.store.load_learning_candidate(candidate_id)
        candidate.state = PromotionState.REJECTED
        candidate.rationale = reason.strip()
        candidate.updated_at = utc_now()
        self.store.save_learning_candidate(candidate)
        return candidate

    def _collect_experiences(self, agent_id: str, session_ids: list[str]) -> list[ExperienceRecord]:
        experiences: list[ExperienceRecord] = []
        for session_id in session_ids:
            events = self.store.load_events(session_id)
            if not events or events[0].agent_id != agent_id:
                continue
            if not any(event.type == EventType.ACCEPTANCE for event in events):
                continue
            input_text = self._latest_payload(events, EventType.INPUT, "input")
            output_text = self._latest_payload(events, EventType.AGENT_OUTPUT, "content")
            feedback_texts = [str(event.payload.get("feedback", "")) for event in events if event.type == EventType.FEEDBACK]
            experiences.append(
                ExperienceRecord(
                    agent_id=agent_id,
                    session_id=session_id,
                    accepted=True,
                    input_text=input_text,
                    output_text=output_text,
                    feedback_texts=[text for text in feedback_texts if text.strip()],
                )
            )
        return experiences

    def _build_candidates(self, agent_id: str, experiences: list[ExperienceRecord]) -> list[LearningCandidate]:
        candidates: list[LearningCandidate] = []
        agent = self.store.load_agent(agent_id)
        for experience in experiences:
            mem_op, mem_target = self._memory_refinement(agent_id, experience)
            memory_payload = self._memory_payload(experience)
            candidates.append(
                LearningCandidate(
                    agent_id=agent_id,
                    tenant_id=agent.tenant_id,
                    candidate_type=CandidateType.MEMORY,
                    operation=mem_op,
                    target_id=mem_target,
                    payload=memory_payload,
                    source_session_ids=[experience.session_id],
                    confidence=0.65 if experience.feedback_texts else 0.55,
                    risk_level="low",
                    rationale="Derived compact memory from accepted session and feedback.",
                )
            )

            skill_op, skill_target = self._skill_refinement(agent_id, experience)
            skill_payload = self._skill_payload(experience)
            candidates.append(
                LearningCandidate(
                    agent_id=agent_id,
                    tenant_id=agent.tenant_id,
                    candidate_type=CandidateType.SKILL,
                    operation=skill_op,
                    target_id=skill_target,
                    payload=skill_payload,
                    source_session_ids=[experience.session_id],
                    confidence=0.6 if experience.feedback_texts else 0.5,
                    risk_level="low",
                    rationale="Derived reusable procedure skill from accepted trajectory.",
                )
            )
        return candidates

    def _memory_payload(self, experience: ExperienceRecord) -> dict:
        feedback_summary = " ".join(experience.feedback_texts).strip()
        base = feedback_summary or experience.output_text or experience.input_text
        summary = f"Learned from session {experience.session_id}."
        return {
            "content": base[:400],
            "summary": summary,
            "tags": sorted(list(keywords(experience.input_text) | keywords(feedback_summary)))[:8],
            "memory_type": MemoryType.FEEDBACK.value if feedback_summary else MemoryType.SEMANTIC.value,
        }

    def _skill_payload(self, experience: ExperienceRecord) -> dict:
        joined_feedback = " ".join(experience.feedback_texts).strip()
        activation = sorted(list(keywords(experience.input_text) | keywords(joined_feedback)))[:8]
        name_seed = "_".join(activation[:2]) if activation else "session_skill"
        name = f"skill_{name_seed}"
        procedure = [
            "Identify the task objective from user input.",
            "Apply company preference signals from feedback when available.",
            "Ask follow-up questions if required details are missing.",
        ]
        if joined_feedback:
            procedure.append(f"Prioritize this correction: {joined_feedback[:120]}")
        return {
            "name": name[:60],
            "description": f"Procedure learned from accepted session {experience.session_id}.",
            "activation_keywords": activation,
            "procedure": procedure,
            "constraints": ["Do not invent unsupported facts.", "Prefer explicit user feedback over old memory."],
        }

    def _memory_refinement(self, agent_id: str, experience: ExperienceRecord) -> tuple[RefinementOp, str | None]:
        existing = self.memory.list(agent_id)
        content_terms = keywords(" ".join(experience.feedback_texts) or experience.output_text)
        if "deprecated" in content_terms or "remove" in content_terms:
            if existing:
                return RefinementOp.DELETE, existing[0].memory_id
        for item in existing:
            overlap = len(content_terms.intersection(keywords(item.content)))
            if overlap >= 3:
                return RefinementOp.UPDATE, item.memory_id
        if len(existing) >= 2:
            recent = sorted(existing, key=lambda item: item.updated_at, reverse=True)[:2]
            overlap = len(keywords(recent[0].content).intersection(keywords(recent[1].content)))
            if overlap >= 3:
                return RefinementOp.COMBINE, f"{recent[0].memory_id},{recent[1].memory_id}"
        return RefinementOp.ADD, None

    def _skill_refinement(self, agent_id: str, experience: ExperienceRecord) -> tuple[RefinementOp, str | None]:
        existing = self.skills.list(agent_id)
        if not existing:
            return RefinementOp.ADD, None
        input_terms = keywords(experience.input_text)
        for skill in existing:
            overlap = len(input_terms.intersection(set(skill.activation_keywords)))
            if overlap >= 2:
                return RefinementOp.UPDATE, skill.skill_id
        if len(existing) >= 2:
            return RefinementOp.COMBINE, f"{existing[0].skill_id},{existing[1].skill_id}"
        return RefinementOp.ADD, None

    @staticmethod
    def _latest_payload(events: list, event_type: EventType, key: str) -> str:
        for event in reversed(events):
            if event.type == event_type:
                payload = event.payload
                if event_type == EventType.AGENT_OUTPUT:
                    payload = payload if isinstance(payload, dict) else {}
                    if isinstance(payload.get("confidence"), dict):
                        return str(payload.get(key, ""))
                return str(payload.get(key, ""))
        return ""

    def _replay_scores(self, candidate: LearningCandidate) -> tuple[float, float, int, float]:
        experiences = self._collect_experiences(candidate.agent_id, candidate.source_session_ids)
        if not experiences:
            return 0.0, 0.0, 0, 0.0
        baseline_total = 0.0
        candidate_total = 0.0
        activation_mismatches = 0
        for exp in experiences:
            baseline = self._baseline_score(exp)
            cand = self._candidate_score(exp, candidate)
            baseline_total += baseline
            candidate_total += cand
            if candidate.candidate_type == CandidateType.SKILL:
                terms = keywords(exp.input_text + " " + " ".join(exp.feedback_texts))
                activations = {str(v).lower() for v in candidate.payload.get("activation_keywords", [])}
                if terms and not terms.intersection(activations):
                    activation_mismatches += 1
        replay_samples = len(experiences)
        baseline_score = baseline_total / replay_samples
        candidate_score = candidate_total / replay_samples
        activation_error = activation_mismatches / replay_samples if replay_samples else 0.0
        return baseline_score, candidate_score, replay_samples, activation_error

    @staticmethod
    def _baseline_score(experience: ExperienceRecord) -> float:
        score = 0.45
        if experience.feedback_texts:
            score += 0.04
        if len(experience.input_text.strip()) > 20:
            score += 0.02
        return min(score, 1.0)

    @staticmethod
    def _candidate_score(experience: ExperienceRecord, candidate: LearningCandidate) -> float:
        score = 0.53
        src = " ".join(experience.feedback_texts) + " " + experience.input_text
        terms = keywords(src)
        payload_terms = keywords(" ".join(str(v) for v in candidate.payload.values()))
        overlap = len(terms.intersection(payload_terms))
        score += min(overlap * 0.01, 0.10)
        score += max(0.0, candidate.confidence - 0.5) * 0.10
        return min(score, 1.0)

    def _apply_candidate_and_collect_actions(self, candidate: LearningCandidate) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if candidate.candidate_type == CandidateType.MEMORY:
            actions.extend(self._promote_memory_candidate(candidate))
        else:
            actions.extend(self._promote_skill_candidate(candidate))
        return actions

    def _promote_memory_candidate(self, candidate: LearningCandidate) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if candidate.operation == RefinementOp.COMBINE and candidate.target_id:
            ids = [value.strip() for value in candidate.target_id.split(",") if value.strip()]
            combined_parts: list[str] = []
            for memory_id in ids:
                memory = self.store.load_memory(candidate.agent_id, memory_id)
                actions.append({"kind": "memory_snapshot", "memory": memory.model_dump(mode="json")})
                combined_parts.append(memory.content)
                memory.status = ResourceStatus.DEPRECATED
                memory.updated_at = utc_now()
                self.store.save_memory(memory)
            created = self.memory.create(
                agent_id=candidate.agent_id,
                content=(" ".join(combined_parts).strip()[:500]) or str(candidate.payload.get("content", "")),
                summary=str(candidate.payload.get("summary", "Combined from prior memories.")),
                tags=[str(value) for value in candidate.payload.get("tags", [])],
                memory_type=MemoryType(str(candidate.payload.get("memory_type", MemoryType.SEMANTIC.value))),
                confidence=candidate.confidence,
                status=ResourceStatus.ACTIVE,
            )
            actions.append({"kind": "memory_created", "agent_id": candidate.agent_id, "memory_id": created.memory_id})
            return actions

        if candidate.operation == RefinementOp.DELETE and candidate.target_id:
            target = self.store.load_memory(candidate.agent_id, candidate.target_id)
            actions.append({"kind": "memory_snapshot", "memory": target.model_dump(mode="json")})
            target.status = ResourceStatus.DEPRECATED
            target.updated_at = utc_now()
            self.store.save_memory(target)
            return actions

        if candidate.operation == RefinementOp.UPDATE and candidate.target_id:
            target = self.store.load_memory(candidate.agent_id, candidate.target_id)
            actions.append({"kind": "memory_snapshot", "memory": target.model_dump(mode="json")})
            target.content = str(candidate.payload.get("content", target.content))
            target.summary = str(candidate.payload.get("summary", target.summary))
            target.tags = [str(value) for value in candidate.payload.get("tags", target.tags)]
            target.updated_at = utc_now()
            self.store.save_memory(target)
            return actions

        content = str(candidate.payload.get("content", "")).strip()
        if not content:
            raise ValueError("Memory candidate has empty content.")
        created = self.memory.create(
            agent_id=candidate.agent_id,
            content=content,
            summary=str(candidate.payload.get("summary", "")),
            tags=[str(value) for value in candidate.payload.get("tags", [])],
            memory_type=MemoryType(str(candidate.payload.get("memory_type", MemoryType.SEMANTIC.value))),
            confidence=candidate.confidence,
            status=ResourceStatus.ACTIVE,
        )
        actions.append({"kind": "memory_created", "agent_id": candidate.agent_id, "memory_id": created.memory_id})
        return actions

    def _promote_skill_candidate(self, candidate: LearningCandidate) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        if candidate.operation == RefinementOp.COMBINE and candidate.target_id:
            ids = [value.strip() for value in candidate.target_id.split(",") if value.strip()]
            existing = [self.store.load_skill(skill_id) for skill_id in ids]
            for skill in existing:
                actions.append({"kind": "skill_snapshot", "skill": skill.model_dump(mode="json")})
                skill.status = ResourceStatus.DEPRECATED
                skill.updated_at = utc_now()
                self.store.save_skill(skill)
            name = str(candidate.payload.get("name", "combined_skill")).strip() or "combined_skill"
            description = str(
                candidate.payload.get("description", "Combined skill created from validated candidates.")
            ).strip()
            activation_keywords = [term for skill in existing for term in skill.activation_keywords]
            procedure = [step for skill in existing for step in skill.procedure]
            constraints = [item for skill in existing for item in skill.constraints]
            new_skill = self.skills.create(
                name=name[:60],
                description=description or "Combined skill.",
                activation_keywords=sorted(set(activation_keywords)),
                procedure=procedure or [str(value) for value in candidate.payload.get("procedure", [])],
                constraints=constraints or [str(value) for value in candidate.payload.get("constraints", [])],
                confidence=candidate.confidence,
                status=ResourceStatus.ACTIVE,
            )
            self.skills.bind(candidate.agent_id, new_skill.skill_id)
            actions.append({"kind": "skill_created", "skill_id": new_skill.skill_id})
            actions.append({"kind": "skill_bound", "agent_id": candidate.agent_id, "skill_id": new_skill.skill_id})
            return actions

        if candidate.operation == RefinementOp.DELETE and candidate.target_id:
            skill = self.store.load_skill(candidate.target_id)
            actions.append({"kind": "skill_snapshot", "skill": skill.model_dump(mode="json")})
            skill.status = ResourceStatus.DEPRECATED
            skill.updated_at = utc_now()
            self.store.save_skill(skill)
            return actions

        if candidate.operation == RefinementOp.UPDATE and candidate.target_id:
            skill = self.store.load_skill(candidate.target_id)
            actions.append({"kind": "skill_snapshot", "skill": skill.model_dump(mode="json")})
            skill.name = str(candidate.payload.get("name", skill.name))
            skill.description = str(candidate.payload.get("description", skill.description))
            skill.activation_keywords = [str(value) for value in candidate.payload.get("activation_keywords", skill.activation_keywords)]
            skill.procedure = [str(value) for value in candidate.payload.get("procedure", skill.procedure)]
            skill.constraints = [str(value) for value in candidate.payload.get("constraints", skill.constraints)]
            skill.updated_at = utc_now()
            self.store.save_skill(skill)
            self.skills.bind(candidate.agent_id, skill.skill_id)
            actions.append({"kind": "skill_bound", "agent_id": candidate.agent_id, "skill_id": skill.skill_id})
            return actions

        name = str(candidate.payload.get("name", "")).strip()
        description = str(candidate.payload.get("description", "")).strip()
        if not name or not description:
            raise ValueError("Skill candidate has invalid name/description.")
        skill = self.skills.create(
            name=name,
            description=description,
            activation_keywords=[str(value) for value in candidate.payload.get("activation_keywords", [])],
            procedure=[str(value) for value in candidate.payload.get("procedure", [])],
            constraints=[str(value) for value in candidate.payload.get("constraints", [])],
            confidence=candidate.confidence,
            status=ResourceStatus.ACTIVE,
        )
        self.skills.bind(candidate.agent_id, skill.skill_id)
        actions.append({"kind": "skill_created", "skill_id": skill.skill_id})
        actions.append({"kind": "skill_bound", "agent_id": candidate.agent_id, "skill_id": skill.skill_id})
        return actions

    def _revert_actions(self, actions: list[dict[str, Any]]) -> None:
        for action in reversed(actions):
            kind = action.get("kind")
            if kind == "memory_created":
                memory = self.store.load_memory(str(action["agent_id"]), str(action["memory_id"]))
                memory.status = ResourceStatus.DEPRECATED
                memory.updated_at = utc_now()
                self.store.save_memory(memory)
            elif kind == "memory_snapshot":
                raw = action["memory"]
                memory = MemoryItem.model_validate(raw)
                self.store.save_memory(memory)
            elif kind == "skill_created":
                skill = self.store.load_skill(action["skill_id"])
                skill.status = ResourceStatus.DEPRECATED
                skill.updated_at = utc_now()
                self.store.save_skill(skill)
            elif kind == "skill_snapshot":
                raw = action["skill"]
                skill = SkillDefinition.model_validate(raw)
                self.store.save_skill(skill)
