"""Quality-Gated Skill Lifecycle — four gates and four trust tiers.

Controls what capabilities an agent can acquire, how much trust new
capabilities receive, and how trust changes over time. A capability
enters at T1 (sandboxed) and can only promote through demonstrated
reliability. Demotion is always possible; promotion is never automatic.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Optional, Callable


class TrustTier(IntEnum):
    T1_SANDBOXED = 1
    T2_VALIDATED = 2
    T3_PROMOTED = 3
    T4_TRUSTED = 4


class GateResult(Enum):
    PASSED = "passed"
    REJECTED_DISCARD = "rejected_discard"
    REJECTED_DUPLICATE = "rejected_duplicate"
    REJECTED_BENCHMARK = "rejected_benchmark"


class PromotionResult(Enum):
    PROMOTED = "promoted"
    NOT_ELIGIBLE = "not_eligible"
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"


@dataclass
class SkillCandidate:
    name: str
    description: str
    source: str  # "human", "self_generated", "imported"
    test_cases: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SkillRecord:
    id: str
    name: str
    description: str
    source: str
    trust_tier: TrustTier = TrustTier.T1_SANDBOXED
    invocation_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    promoted_at: Optional[float] = None
    demoted_at: Optional[float] = None
    retired: bool = False
    retirement_reason: Optional[str] = None


@dataclass
class InvocationResult:
    success: bool
    duration_ms: float = 0.0
    error: Optional[str] = None


@dataclass
class PromotionCriteria:
    """Configurable thresholds for tier promotion."""
    t1_to_t2_invocations: int = 10
    t1_to_t2_max_failures: int = 0
    t2_to_t3_invocations: int = 50
    t2_to_t3_max_failure_rate: float = 0.02
    t2_to_t3_min_days: int = 30
    t3_to_t4_invocations: int = 200
    t3_to_t4_max_failure_rate: float = 0.01


class SkillLifecycle:
    """Four gates control entry. Four tiers control trust. Demotion is immediate."""

    def __init__(
        self,
        criteria: Optional[PromotionCriteria] = None,
        similarity_threshold: float = 0.85,
        similarity_fn: Optional[Callable[[str, str], float]] = None,
    ):
        self._skills: dict[str, SkillRecord] = {}
        self._criteria = criteria or PromotionCriteria()
        self._similarity_threshold = similarity_threshold
        self._similarity_fn = similarity_fn or self._default_similarity

    # ─── Four Gates ────────────────────────────────────────────

    def submit_candidate(self, candidate: SkillCandidate, safety_check: Optional[Callable] = None) -> tuple[GateResult, Optional[str]]:
        """Run candidate through all four gates. Returns (result, skill_id or None)."""

        # Gate 1: Discard
        if safety_check and not safety_check(candidate):
            return GateResult.REJECTED_DISCARD, None
        if not candidate.name or not candidate.description:
            return GateResult.REJECTED_DISCARD, None

        # Gate 2: Similarity
        for existing in self._skills.values():
            if existing.retired:
                continue
            score = self._similarity_fn(candidate.description, existing.description)
            if score >= self._similarity_threshold:
                return GateResult.REJECTED_DUPLICATE, None

        # Gate 3: Benchmark
        if candidate.test_cases:
            for test in candidate.test_cases:
                expected = test.get("expected")
                actual = test.get("actual")
                if expected is not None and actual is not None and expected != actual:
                    return GateResult.REJECTED_BENCHMARK, None

        # Gate 4: Trust Assignment (always T1)
        skill_id = str(uuid.uuid4())[:8]
        record = SkillRecord(
            id=skill_id,
            name=candidate.name,
            description=candidate.description,
            source=candidate.source,
            trust_tier=TrustTier.T1_SANDBOXED,
        )
        self._skills[skill_id] = record
        return GateResult.PASSED, skill_id

    # ─── Invocation Tracking ───────────────────────────────────

    def record_invocation(self, skill_id: str, result: InvocationResult) -> None:
        """Record a skill invocation outcome."""
        skill = self._skills.get(skill_id)
        if skill and not skill.retired:
            skill.invocation_count += 1
            if not result.success:
                skill.failure_count += 1

    def can_invoke(self, skill_id: str) -> bool:
        """Check if a skill can be invoked given its trust tier."""
        skill = self._skills.get(skill_id)
        if skill is None or skill.retired:
            return False
        return True  # All tiers can be invoked; tier affects context (sandbox vs production)

    # ─── Promotion ─────────────────────────────────────────────

    def check_promotion(self, skill_id: str) -> PromotionResult:
        """Check if a skill is eligible for promotion."""
        skill = self._skills.get(skill_id)
        if skill is None or skill.retired:
            return PromotionResult.NOT_ELIGIBLE

        c = self._criteria

        if skill.trust_tier == TrustTier.T1_SANDBOXED:
            if skill.invocation_count >= c.t1_to_t2_invocations and skill.failure_count <= c.t1_to_t2_max_failures:
                return PromotionResult.PROMOTED
        elif skill.trust_tier == TrustTier.T2_VALIDATED:
            failure_rate = skill.failure_count / max(1, skill.invocation_count)
            days_at_tier = (time.time() - (skill.promoted_at or skill.created_at)) / 86400
            if (skill.invocation_count >= c.t2_to_t3_invocations
                    and failure_rate <= c.t2_to_t3_max_failure_rate
                    and days_at_tier >= c.t2_to_t3_min_days):
                return PromotionResult.PROMOTED
        elif skill.trust_tier == TrustTier.T3_PROMOTED:
            failure_rate = skill.failure_count / max(1, skill.invocation_count)
            if (skill.invocation_count >= c.t3_to_t4_invocations
                    and failure_rate <= c.t3_to_t4_max_failure_rate):
                return PromotionResult.REQUIRES_HUMAN_APPROVAL
        # T4 cannot promote further
        return PromotionResult.NOT_ELIGIBLE

    def promote(self, skill_id: str) -> bool:
        """Execute promotion (one tier up). Returns success."""
        skill = self._skills.get(skill_id)
        if skill is None or skill.retired:
            return False
        if skill.trust_tier >= TrustTier.T4_TRUSTED:
            return False
        skill.trust_tier = TrustTier(skill.trust_tier + 1)
        skill.promoted_at = time.time()
        return True

    # ─── Demotion ──────────────────────────────────────────────

    def demote(self, skill_id: str, reason: str) -> bool:
        """Immediately demote a skill one tier. Returns success."""
        skill = self._skills.get(skill_id)
        if skill is None or skill.retired:
            return False
        if skill.trust_tier <= TrustTier.T1_SANDBOXED:
            return False
        skill.trust_tier = TrustTier(skill.trust_tier - 1)
        skill.demoted_at = time.time()
        return True

    def retire(self, skill_id: str, reason: str) -> bool:
        """Permanently retire a skill."""
        skill = self._skills.get(skill_id)
        if skill is None:
            return False
        skill.retired = True
        skill.retirement_reason = reason
        return True

    # ─── Read Interface ────────────────────────────────────────

    def get_skill(self, skill_id: str) -> Optional[SkillRecord]:
        return self._skills.get(skill_id)

    def list_by_tier(self, tier: TrustTier) -> list[SkillRecord]:
        return [s for s in self._skills.values() if s.trust_tier == tier and not s.retired]

    def get_failure_rate(self, skill_id: str) -> float:
        skill = self._skills.get(skill_id)
        if skill is None or skill.invocation_count == 0:
            return 0.0
        return skill.failure_count / skill.invocation_count

    # ─── Internal ──────────────────────────────────────────────

    @staticmethod
    def _default_similarity(a: str, b: str) -> float:
        """Simple word-overlap similarity. Replace with embeddings in production."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)
