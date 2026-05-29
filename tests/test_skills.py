"""Tests for skill lifecycle — gates, trust tiers, promotion, demotion."""

import time

import pytest

from shard.skills import (
    GateResult,
    InvocationResult,
    PromotionCriteria,
    PromotionResult,
    SkillCandidate,
    SkillLifecycle,
    TrustTier,
)


class TestGateDiscard:
    def test_empty_name_rejected(self):
        lc = SkillLifecycle()
        candidate = SkillCandidate(name="", description="does stuff", source="human")
        result, _ = lc.submit_candidate(candidate)
        assert result == GateResult.REJECTED_DISCARD

    def test_safety_check_rejects(self):
        lc = SkillLifecycle()
        candidate = SkillCandidate(name="dangerous", description="bad", source="self_generated")
        result, _ = lc.submit_candidate(candidate, safety_check=lambda c: False)
        assert result == GateResult.REJECTED_DISCARD

    def test_valid_candidate_passes_discard(self):
        lc = SkillLifecycle()
        candidate = SkillCandidate(name="helper", description="helps with tasks", source="human")
        result, skill_id = lc.submit_candidate(candidate)
        assert result == GateResult.PASSED
        assert skill_id is not None


class TestGateSimilarity:
    def test_duplicate_rejected(self):
        lc = SkillLifecycle(similarity_threshold=0.5)
        c1 = SkillCandidate(name="file writer", description="writes files to disk", source="human")
        c2 = SkillCandidate(name="disk writer", description="writes files to disk", source="human")
        lc.submit_candidate(c1)
        result, _ = lc.submit_candidate(c2)
        assert result == GateResult.REJECTED_DUPLICATE

    def test_different_skill_passes(self):
        lc = SkillLifecycle(similarity_threshold=0.8)
        c1 = SkillCandidate(name="file writer", description="writes files to disk", source="human")
        c2 = SkillCandidate(name="email sender", description="sends emails via SMTP", source="human")
        lc.submit_candidate(c1)
        result, _ = lc.submit_candidate(c2)
        assert result == GateResult.PASSED


class TestGateBenchmark:
    def test_failing_test_case_rejects(self):
        lc = SkillLifecycle()
        candidate = SkillCandidate(
            name="calculator",
            description="does math",
            source="self_generated",
            test_cases=[{"expected": 4, "actual": 5}],
        )
        result, _ = lc.submit_candidate(candidate)
        assert result == GateResult.REJECTED_BENCHMARK

    def test_passing_test_case_passes(self):
        lc = SkillLifecycle()
        candidate = SkillCandidate(
            name="calculator",
            description="does math",
            source="self_generated",
            test_cases=[{"expected": 4, "actual": 4}],
        )
        result, _ = lc.submit_candidate(candidate)
        assert result == GateResult.PASSED


class TestTrustAssignment:
    def test_all_new_skills_start_at_t1(self):
        lc = SkillLifecycle()
        _, skill_id = lc.submit_candidate(
            SkillCandidate(name="new", description="brand new skill", source="human")
        )
        assert lc.get_skill(skill_id).trust_tier == TrustTier.T1_SANDBOXED

    def test_source_does_not_affect_initial_tier(self):
        lc = SkillLifecycle()
        _, sid = lc.submit_candidate(
            SkillCandidate(name="imported", description="from trusted source", source="imported")
        )
        assert lc.get_skill(sid).trust_tier == TrustTier.T1_SANDBOXED


class TestPromotion:
    def test_t1_to_t2_promotion(self):
        lc = SkillLifecycle(criteria=PromotionCriteria(t1_to_t2_invocations=3, t1_to_t2_max_failures=0))
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        for _ in range(3):
            lc.record_invocation(sid, InvocationResult(success=True))
        assert lc.check_promotion(sid) == PromotionResult.PROMOTED
        assert lc.promote(sid) is True
        assert lc.get_skill(sid).trust_tier == TrustTier.T2_VALIDATED

    def test_t1_promotion_blocked_by_failure(self):
        lc = SkillLifecycle(criteria=PromotionCriteria(t1_to_t2_invocations=3, t1_to_t2_max_failures=0))
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        lc.record_invocation(sid, InvocationResult(success=True))
        lc.record_invocation(sid, InvocationResult(success=False))
        lc.record_invocation(sid, InvocationResult(success=True))
        assert lc.check_promotion(sid) == PromotionResult.NOT_ELIGIBLE

    def test_t3_to_t4_requires_human(self):
        lc = SkillLifecycle(criteria=PromotionCriteria(
            t1_to_t2_invocations=1, t1_to_t2_max_failures=0,
            t2_to_t3_invocations=1, t2_to_t3_max_failure_rate=1.0, t2_to_t3_min_days=0,
            t3_to_t4_invocations=1, t3_to_t4_max_failure_rate=1.0,
        ))
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        lc.record_invocation(sid, InvocationResult(success=True))
        lc.promote(sid)  # T1 -> T2
        lc.promote(sid)  # T2 -> T3
        assert lc.check_promotion(sid) == PromotionResult.REQUIRES_HUMAN_APPROVAL

    def test_t4_cannot_promote_further(self):
        lc = SkillLifecycle(criteria=PromotionCriteria(
            t1_to_t2_invocations=1, t1_to_t2_max_failures=0,
            t2_to_t3_invocations=1, t2_to_t3_max_failure_rate=1.0, t2_to_t3_min_days=0,
            t3_to_t4_invocations=1, t3_to_t4_max_failure_rate=1.0,
        ))
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        lc.record_invocation(sid, InvocationResult(success=True))
        lc.promote(sid)  # T1 -> T2
        lc.promote(sid)  # T2 -> T3
        lc.promote(sid)  # T3 -> T4
        assert lc.promote(sid) is False  # Can't go higher


class TestDemotion:
    def test_demote_reduces_tier(self):
        lc = SkillLifecycle(criteria=PromotionCriteria(t1_to_t2_invocations=1, t1_to_t2_max_failures=0))
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        lc.record_invocation(sid, InvocationResult(success=True))
        lc.promote(sid)
        assert lc.get_skill(sid).trust_tier == TrustTier.T2_VALIDATED
        lc.demote(sid, "failure spike")
        assert lc.get_skill(sid).trust_tier == TrustTier.T1_SANDBOXED

    def test_cannot_demote_below_t1(self):
        lc = SkillLifecycle()
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        assert lc.demote(sid, "reason") is False

    def test_retire_skill(self):
        lc = SkillLifecycle()
        _, sid = lc.submit_candidate(SkillCandidate(name="s", description="skill", source="human"))
        lc.retire(sid, "no longer needed")
        assert lc.get_skill(sid).retired is True
        assert lc.can_invoke(sid) is False

    def test_list_by_tier(self):
        lc = SkillLifecycle()
        lc.submit_candidate(SkillCandidate(name="a", description="alpha skill", source="human"))
        lc.submit_candidate(SkillCandidate(name="b", description="beta skill", source="human"))
        assert len(lc.list_by_tier(TrustTier.T1_SANDBOXED)) == 2
        assert len(lc.list_by_tier(TrustTier.T2_VALIDATED)) == 0
