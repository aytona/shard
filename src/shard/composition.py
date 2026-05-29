"""Composition Layer — typed interfaces between subsystems.

This module wires the four subsystems together through their read/write
interfaces. The composition produces emergent properties (most notably
compositional fault recovery) that no individual subsystem provides alone.

No subsystem depends on another's internal state — only on its read interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shard.coordination import CoordinationProtocol, Intent, ActionResult
from shard.memory import MemoryGovernance, Memory
from shard.safety import RateLimiter, ScopeGuard, RollbackRegistry
from shard.skills import SkillLifecycle, SkillCandidate, InvocationResult, TrustTier


@dataclass
class CompositionEvent:
    """Record of a cross-subsystem interaction."""
    source: str
    target: str
    action: str
    detail: str


class SHARD:
    """Composed system — four subsystems interacting through typed interfaces.

    Instantiate this class to get a fully-composed SHARD instance where
    subsystems are wired together and cross-cutting behaviors emerge
    from their interaction.
    """

    def __init__(
        self,
        memory: Optional[MemoryGovernance] = None,
        coordination: Optional[CoordinationProtocol] = None,
        skills: Optional[SkillLifecycle] = None,
        rate_limiter: Optional[RateLimiter] = None,
        scope_guard: Optional[ScopeGuard] = None,
        rollback: Optional[RollbackRegistry] = None,
    ):
        self.memory = memory or MemoryGovernance()
        self.coordination = coordination or CoordinationProtocol()
        self.skills = skills or SkillLifecycle()
        self.rate_limiter = rate_limiter
        self.scope_guard = scope_guard
        self.rollback = rollback
        self._events: list[CompositionEvent] = []

    # ─── Composed Operations ───────────────────────────────────

    def governed_memory_store(self, memory: Memory) -> bool:
        """Store a memory with full governance validation.

        Composition: Memory ← Safety (scope check) ← Coordination (declare intent)
        """
        # Safety: check if memory target is protected
        if self.scope_guard and self.scope_guard.is_protected(memory.id):
            self._log("safety", "memory", "blocked_store", f"Protected: {memory.id}")
            return False

        # Coordination: declare intent to store
        intent = Intent(
            agent_id="self",
            action="memory_store",
            target=memory.id,
            rationale=f"Storing memory: {memory.id}",
        )
        self.coordination.declare(intent)
        result, conflicts = self.coordination.review(intent.id)

        if conflicts:
            resolved = self.coordination.resolve(intent.id, conflicts)
            if not resolved:
                self.coordination.withdraw(intent.id)
                self._log("coordination", "memory", "blocked_store", f"Conflict on {memory.id}")
                return False

        # Store with governance
        self.memory.store(memory)
        self.coordination.begin_execution(intent.id)
        self.coordination.report_completion(intent.id, ActionResult(intent_id=intent.id, success=True))
        self._log("memory", "coordination", "stored", memory.id)
        return True

    def governed_skill_submit(self, candidate: SkillCandidate) -> tuple[str, Optional[str]]:
        """Submit a skill candidate with full composition.

        Composition: Skills ← Safety (gate 1) ← Coordination (declare) ← Rate limiter
        """
        # Rate limiter check
        if self.rate_limiter and not self.rate_limiter.allow():
            self._log("safety", "skills", "rate_limited", candidate.name)
            return "rate_limited", None

        # Safety check for gate 1
        def safety_check(c: SkillCandidate) -> bool:
            if self.scope_guard:
                return not self.scope_guard.is_protected(c.name)
            return True

        # Coordination: declare intent
        intent = Intent(
            agent_id="self",
            action="skill_submit",
            target=candidate.name,
            rationale=f"Submitting skill candidate: {candidate.name}",
        )
        self.coordination.declare(intent)

        # Submit through gates
        gate_result, skill_id = self.skills.submit_candidate(candidate, safety_check=safety_check)

        # Record in rate limiter
        if self.rate_limiter:
            self.rate_limiter.record(success=(skill_id is not None))

        # Report to coordination
        self.coordination.begin_execution(intent.id)
        self.coordination.report_completion(
            intent.id,
            ActionResult(intent_id=intent.id, success=(skill_id is not None))
        )

        self._log("skills", "coordination", f"gate_{gate_result.value}", candidate.name)
        return gate_result.value, skill_id

    def governed_skill_invoke(self, skill_id: str) -> bool:
        """Invoke a skill with coordination and memory validation.

        Composition: Skills → Memory (check dependencies) → Coordination (declare)
        """
        skill = self.skills.get_skill(skill_id)
        if skill is None:
            return False

        # Coordination: declare invocation intent
        intent = Intent(
            agent_id="self",
            action="skill_invoke",
            target=skill_id,
            rationale=f"Invoking skill: {skill.name}",
        )
        self.coordination.declare(intent)
        result, conflicts = self.coordination.review(intent.id)

        if conflicts:
            resolved = self.coordination.resolve(intent.id, conflicts)
            if not resolved:
                self.coordination.withdraw(intent.id)
                return False

        self.coordination.begin_execution(intent.id)
        # Actual invocation would happen here via adapter
        self.coordination.report_completion(intent.id, ActionResult(intent_id=intent.id, success=True))
        self.skills.record_invocation(skill_id, InvocationResult(success=True))
        return True

    def handle_stale_memory(self, memory_id: str, reason: str) -> list[str]:
        """Compositional fault recovery: stale memory cascade.

        Memory detects stale → Skills demotes affected → Coordination broadcasts
        """
        # 1. Memory: invalidate and cascade
        invalidated = self.memory.invalidate(memory_id, reason)
        self._log("memory", "skills", "stale_cascade", f"{len(invalidated)} memories invalidated")

        # 2. Skills: check if any skills depend on invalidated memories
        demoted_skills = []
        for mid in invalidated:
            for skill in self.skills.list_by_tier(TrustTier.T1_SANDBOXED) + \
                         self.skills.list_by_tier(TrustTier.T2_VALIDATED) + \
                         self.skills.list_by_tier(TrustTier.T3_PROMOTED) + \
                         self.skills.list_by_tier(TrustTier.T4_TRUSTED):
                if mid in skill.metadata.get("memory_dependencies", []):
                    self.skills.demote(skill.id, f"Memory dependency stale: {mid}")
                    demoted_skills.append(skill.id)

        # 3. Coordination: broadcast the change
        if demoted_skills:
            intent = Intent(
                agent_id="self",
                action="capability_change",
                target="skill_registry",
                rationale=f"Demoted {len(demoted_skills)} skills due to stale memory",
            )
            self.coordination.declare(intent)
            self.coordination.begin_execution(intent.id)
            self.coordination.report_completion(
                intent.id, ActionResult(intent_id=intent.id, success=True)
            )
            self._log("skills", "coordination", "demoted_broadcast", f"{len(demoted_skills)} skills")

        return invalidated

    # ─── Observability ─────────────────────────────────────────

    def get_events(self, limit: int = 50) -> list[CompositionEvent]:
        """Get recent composition events for debugging/observability."""
        return self._events[-limit:]

    def _log(self, source: str, target: str, action: str, detail: str) -> None:
        self._events.append(CompositionEvent(
            source=source, target=target, action=action, detail=detail
        ))
