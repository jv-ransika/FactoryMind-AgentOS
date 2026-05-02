from __future__ import annotations

from agent_os.protocol import ResourceStatus, RetrievalResult, RetrievedSkill, SkillDefinition
from agent_os.retrieval import keyword_overlap
from agent_os.storage import DomainStore


class SkillManager:
    def __init__(self, store: DomainStore) -> None:
        self.store = store

    def create(
        self,
        name: str,
        description: str,
        owner_agent_id: str | None = None,
        bind_agent_id: str | None = None,
        activation_keywords: list[str] | None = None,
        procedure: list[str] | None = None,
        constraints: list[str] | None = None,
        confidence: float = 0.5,
        status: ResourceStatus = ResourceStatus.ACTIVE,
    ) -> SkillDefinition:
        if owner_agent_id is not None:
            owner_agent = self.store.load_agent(owner_agent_id)
        else:
            owner_agent = None
        if bind_agent_id is not None:
            bind_agent = self.store.load_agent(bind_agent_id)
        else:
            bind_agent = None
        tenant_id = owner_agent.tenant_id if owner_agent is not None else (bind_agent.tenant_id if bind_agent is not None else "default")
        skill = SkillDefinition(
            tenant_id=tenant_id,
            owner_agent_id=owner_agent_id,
            name=name,
            description=description,
            activation_keywords=activation_keywords or [],
            procedure=procedure or [],
            constraints=constraints or [],
            confidence=confidence,
            status=status,
        )
        self.store.save_skill(skill)
        if bind_agent_id is not None:
            self.store.bind_skill(bind_agent_id, skill.skill_id)
        return skill

    def bind(self, agent_id: str, skill_id: str) -> None:
        self.store.load_agent(agent_id)
        self.store.load_skill(skill_id)
        self.store.bind_skill(agent_id, skill_id)

    def list_library(self) -> list[SkillDefinition]:
        return self.store.list_skills()

    def list(self, agent_id: str) -> list[SkillDefinition]:
        self.store.load_agent(agent_id)
        skill_ids = self.store.list_bound_skill_ids(agent_id)
        skills: list[SkillDefinition] = []
        for skill_id in skill_ids:
            try:
                skills.append(self.store.load_skill(skill_id))
            except FileNotFoundError:
                continue
        return skills

    def retrieve(self, agent_id: str, query: str, limit: int = 5) -> list[RetrievedSkill]:
        skills = [
            skill
            for skill in self.list(agent_id)
            if skill.status == ResourceStatus.ACTIVE
        ]
        results: list[RetrievedSkill] = []
        for skill in skills:
            matched, score = keyword_overlap(
                query,
                [
                    skill.name,
                    skill.description,
                    " ".join(skill.activation_keywords),
                    " ".join(skill.procedure),
                    " ".join(skill.constraints),
                ],
            )
            if score > 0:
                results.append(
                    RetrievedSkill(
                        skill=skill,
                        retrieval=RetrievalResult(query=query, matched_terms=matched, score=score),
                    )
                )

        return sorted(
            results,
            key=lambda result: (result.retrieval.score, result.skill.confidence, result.skill.updated_at),
            reverse=True,
        )[:limit]
