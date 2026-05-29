# Quality-Gated Skill Lifecycle Specification

## Purpose

Control what capabilities an agent can acquire, how much trust new capabilities receive, and how trust changes over time based on demonstrated reliability.

## Problem Statement

An agent that can freely acquire capabilities faces:
- **Capability pollution** — Accumulating low-quality or redundant skills
- **Trust inflation** — New, unvalidated capabilities receiving the same authority as proven ones
- **Silent degradation** — Skills that worked once but fail under new conditions
- **Unbounded growth** — No mechanism to retire or demote capabilities

## The Four Gates

Every candidate capability must pass through four sequential gates:

### Gate 1: Discard

**Question:** Should this capability be rejected outright?

Rejection criteria:
- Violates safety constraints
- Contradicts existing validated capabilities
- Targets a domain the agent is not authorized for
- Malformed or incomplete specification

If rejected → candidate is discarded with logged reason. No further processing.

### Gate 2: Similarity

**Question:** Does an equivalent capability already exist?

Detection:
- Semantic similarity against existing skill registry (threshold: configurable, default 0.85)
- Functional overlap analysis (same inputs → same outputs)

If duplicate → candidate is discarded (existing skill retained). If partial overlap → flag for merge consideration.

### Gate 3: Benchmark

**Question:** Does this capability actually work?

Validation:
- Execute against test cases (if provided)
- Verify outputs match expected format
- Check for side effects outside declared scope
- Measure execution time against bounds

If fails → candidate is discarded. If passes → proceeds to trust assignment.

### Gate 4: Trust Assignment

**Question:** What initial trust level should this capability receive?

Assignment criteria:
- Source provenance (human-authored vs. self-generated vs. imported)
- Benchmark performance score
- Scope of capability (narrow = higher initial trust, broad = lower)

All new capabilities enter at T1 (Sandboxed) regardless of source. Trust is earned, never assumed.

## The Four Trust Tiers

| Tier | Name | Permissions | Promotion Criteria |
|------|------|-------------|-------------------|
| T1 | Sandboxed | Execute only in test/sandbox context. Limited invocations per session. | 10+ successful invocations, 0 failures, human review |
| T2 | Validated | Execute in production context. Normal invocation limits. | 50+ invocations, <2% failure rate, 30+ days at T2 |
| T3 | Promoted | Full execution. Can be composed with other skills. | 200+ invocations, <1% failure rate, no safety incidents |
| T4 | Trusted | Full execution. Can be used as dependency by other skills. Can influence self-improvement. | Manual promotion only. Requires explicit human approval. |

### Promotion Rules

- Promotion is never automatic — it requires meeting criteria AND a promotion check
- Promotion checks run periodically (configurable, default: weekly)
- A skill can only promote one tier at a time
- T4 promotion always requires human approval (programmatic enforcement)

### Demotion Rules

- Demotion is immediate upon trigger (no grace period)
- Demotion triggers: failure rate exceeds tier threshold, safety incident, dependency invalidation
- A demoted skill retains its history (can re-promote faster if issues are resolved)
- Demotion cascades: if a T4 skill is demoted, all skills depending on it are re-evaluated

## Interfaces

### Read Interface

```python
class SkillLifecycleRead:
    def get_trust_tier(self, skill_id: str) -> TrustTier
    def get_skill_health(self, skill_id: str) -> SkillHealth
    def list_skills_by_tier(self, tier: TrustTier) -> list[SkillRecord]
    def get_promotion_eligibility(self, skill_id: str) -> EligibilityResult
```

### Write Interface

```python
class SkillLifecycleWrite:
    def submit_candidate(self, candidate: SkillCandidate) -> GateResult
    def record_invocation(self, skill_id: str, result: InvocationResult) -> None
    def request_promotion(self, skill_id: str) -> PromotionResult
    def demote(self, skill_id: str, reason: str) -> None
    def retire(self, skill_id: str, reason: str) -> None
```

## Integration Points

| Subsystem | Interaction |
|-----------|-------------|
| Memory Governance | Skills with stale knowledge dependencies are demoted; memory validation informs benchmark gate |
| Coordination | Skill promotion/demotion is declared as intent; other agents are notified of capability changes |
| Self-Improvement | Self-generated skills enter at T1; improvement proposals that would bypass gates are rejected |
| Safety | Gate 1 consults safety constraints; T4 promotion requires safety review |
