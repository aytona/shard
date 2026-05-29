"""Tests for composition layer — cross-subsystem interactions and fault recovery."""

import tempfile
from pathlib import Path

import pytest

from shard.composition import SHARD
from shard.coordination import CoordinationProtocol, ConflictResolution
from shard.memory import Memory, MemoryGovernance
from shard.safety import RateLimiter, RateLimiterConfig, ScopeGuard
from shard.skills import SkillCandidate, SkillLifecycle, PromotionCriteria, TrustTier


class TestGovernedMemoryStore:
    def test_stores_successfully(self):
        shard = SHARD()
        mem = Memory(id="fact-1", content="the sky is blue")
        assert shard.governed_memory_store(mem) is True
        assert shard.memory.get("fact-1") is not None

    def test_blocked_by_scope_guard(self):
        shard = SHARD(scope_guard=ScopeGuard(["protected-memory"]))
        mem = Memory(id="protected-memory", content="cannot store here")
        assert shard.governed_memory_store(mem) is False

    def test_blocked_by_coordination_conflict(self):
        coord = CoordinationProtocol(resolution_strategy=ConflictResolution.FIRST_DECLARED)
        shard = SHARD(coordination=coord)
        # Pre-declare a conflicting intent on the same target
        from shard.coordination import Intent
        existing = Intent(agent_id="other", action="memory_store", target="shared-fact", rationale="x")
        coord.declare(existing)
        # Now try to store — should conflict
        mem = Memory(id="shared-fact", content="my version")
        assert shard.governed_memory_store(mem) is False


class TestGovernedSkillSubmit:
    def test_submits_successfully(self):
        shard = SHARD()
        result, skill_id = shard.governed_skill_submit(
            SkillCandidate(name="helper", description="helps with tasks", source="human")
        )
        assert result == "passed"
        assert skill_id is not None

    def test_rate_limited(self, tmp_path):
        limiter = RateLimiter(
            tmp_path / "state.json",
            RateLimiterConfig(max_per_session=1, max_per_day=1),
        )
        shard = SHARD(rate_limiter=limiter)
        # First succeeds
        shard.governed_skill_submit(SkillCandidate(name="a", description="first skill", source="human"))
        # Second is rate limited
        result, _ = shard.governed_skill_submit(
            SkillCandidate(name="b", description="second skill", source="human")
        )
        assert result == "rate_limited"

    def test_scope_guard_blocks_protected_name(self):
        shard = SHARD(scope_guard=ScopeGuard(["core-safety"]))
        result, _ = shard.governed_skill_submit(
            SkillCandidate(name="core-safety", description="override safety", source="self_generated")
        )
        assert result == "rejected_discard"


class TestGovernedSkillInvoke:
    def test_invokes_successfully(self):
        shard = SHARD()
        _, sid = shard.skills.submit_candidate(
            SkillCandidate(name="tool", description="a useful tool", source="human")
        )
        assert shard.governed_skill_invoke(sid) is True

    def test_nonexistent_skill_fails(self):
        shard = SHARD()
        assert shard.governed_skill_invoke("nonexistent") is False


class TestCompositionalFaultRecovery:
    def test_stale_memory_cascades_to_skill_demotion(self):
        shard = SHARD(
            skills=SkillLifecycle(criteria=PromotionCriteria(t1_to_t2_invocations=1, t1_to_t2_max_failures=0))
        )
        # Store a memory
        shard.memory.store(Memory(id="api-endpoint", content="https://old.api.com"))

        # Create a skill that depends on that memory
        _, sid = shard.skills.submit_candidate(
            SkillCandidate(
                name="api-caller",
                description="calls the API",
                source="human",
                metadata={"memory_dependencies": ["api-endpoint"]},
            )
        )
        # Promote to T2
        from shard.skills import InvocationResult
        shard.skills.record_invocation(sid, InvocationResult(success=True))
        shard.skills.promote(sid)
        assert shard.skills.get_skill(sid).trust_tier == TrustTier.T2_VALIDATED

        # Now: memory goes stale — should cascade to skill demotion
        invalidated = shard.handle_stale_memory("api-endpoint", "endpoint moved")
        assert "api-endpoint" in invalidated
        assert shard.skills.get_skill(sid).trust_tier == TrustTier.T1_SANDBOXED

    def test_stale_memory_without_skill_deps_no_demotion(self):
        shard = SHARD()
        shard.memory.store(Memory(id="isolated-fact", content="standalone"))
        _, sid = shard.skills.submit_candidate(
            SkillCandidate(name="unrelated", description="no deps", source="human")
        )
        invalidated = shard.handle_stale_memory("isolated-fact", "outdated")
        assert "isolated-fact" in invalidated
        # Skill should be unaffected
        assert shard.skills.get_skill(sid).trust_tier == TrustTier.T1_SANDBOXED


class TestObservability:
    def test_events_logged(self):
        shard = SHARD()
        shard.governed_memory_store(Memory(id="x", content="y"))
        events = shard.get_events()
        assert len(events) > 0
        assert any(e.action == "stored" for e in events)

    def test_events_capped(self):
        shard = SHARD()
        for i in range(100):
            shard.governed_memory_store(Memory(id=f"m{i}", content=f"fact {i}"))
        events = shard.get_events(limit=10)
        assert len(events) == 10
