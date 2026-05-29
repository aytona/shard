# Memory Governance Specification

## Purpose

Memory Governance ensures that an agent's persistent knowledge remains accurate, consistent, and actionable over time. It does not store memories — it governs their quality.

## Problem Statement

Without governance, agent memory degrades through:
- **Staleness** — Facts that were true when stored but are no longer valid
- **Contradiction** — Multiple memories asserting incompatible claims
- **Pollution** — Low-quality or irrelevant information diluting useful knowledge
- **Orphaning** — Memories whose context or dependencies no longer exist

## Interfaces

### Read Interface (exposed to other subsystems)

```python
class MemoryGovernanceRead:
    def is_valid(self, memory_id: str) -> ValidationResult
    def get_staleness_score(self, memory_id: str) -> float  # 0.0 = fresh, 1.0 = stale
    def get_conflicts(self, memory_id: str) -> list[ConflictRecord]
    def get_dependency_chain(self, memory_id: str) -> list[str]
```

### Write Interface (accepts from other subsystems)

```python
class MemoryGovernanceWrite:
    def report_stale(self, memory_id: str, evidence: str) -> None
    def report_conflict(self, memory_a: str, memory_b: str, description: str) -> None
    def invalidate(self, memory_id: str, reason: str) -> None
    def refresh(self, memory_id: str, new_evidence: str) -> None
```

## Staleness Detection

### Detection Triggers

| Trigger | Mechanism |
|---------|-----------|
| Time-based | Memory exceeds configured TTL without refresh |
| Dependency-based | A memory this one depends on was invalidated |
| Contradiction-based | New information conflicts with stored memory |
| External signal | Another subsystem reports the memory is stale |

### Staleness Cascade (Type II)

When a memory is invalidated, all memories that depend on it must be re-evaluated. This is a graph traversal problem:

1. Build dependency graph from `depends_on` annotations
2. Invalidate the root memory
3. For each dependent: re-evaluate validity given the invalidation
4. Propagate recursively until no further invalidations occur

**Bound:** Maximum cascade depth is configurable (default: 5 levels) to prevent runaway invalidation.

## 3D Validation

Every memory is validated across three dimensions:

| Dimension | Question | Check |
|-----------|----------|-------|
| Temporal | Is this still true? | TTL, last-verified timestamp, external signals |
| Semantic | Does this contradict other memories? | Pairwise conflict detection |
| Structural | Is this well-formed and complete? | Schema validation, required fields present |

A memory must pass all three dimensions to be considered valid.

## Conflict Resolution

When two memories conflict:

1. **Recency wins** — More recently verified memory takes precedence (default)
2. **Source authority** — Higher-trust source wins (configurable hierarchy)
3. **Specificity** — More specific claim overrides general claim
4. **Manual** — Flag for human resolution if no rule applies

Resolution strategy is configurable per memory category.

## Integration Points

| Subsystem | Interaction |
|-----------|-------------|
| Skill Lifecycle | Skills with stale knowledge dependencies are demoted |
| Coordination | Memory invalidation is broadcast as an intent (other agents may hold copies) |
| Self-Improvement | New learnings are validated before storage; improvements that contradict validated memory are rejected |
