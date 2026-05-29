# Safety-Constrained Self-Improvement Specification

## Purpose

Enable agents to improve their own capabilities while maintaining hard bounds on what modifications are permissible. Self-improvement is powerful; unconstrained self-improvement is dangerous.

## Problem Statement

An agent that can modify itself faces:
- **Capability drift** — Gradual deviation from intended behavior through accumulated changes
- **Constraint erosion** — The agent modifying its own safety rules
- **Runaway optimization** — Unbounded self-modification consuming resources or producing instability
- **Irreversible damage** — Changes that cannot be undone once applied

## Safety Constraints

### Programmatic Enforcement

Safety constraints are implemented as code, not as prompts or guidelines. An agent cannot reason its way around a programmatic guard.

#### Rate Limiter

```python
class RateLimiter:
    """Hard cap on modifications per time window."""
    max_modifications_per_session: int  # Default: 5
    max_modifications_per_day: int      # Default: 20
    cooldown_after_failure: timedelta   # Default: 1 hour
```

The rate limiter persists state across sessions. It cannot be reset by the agent.

#### Scope Guard

```python
class ScopeGuard:
    """Immutable file/path protection."""
    protected_paths: list[str]  # Files the agent cannot modify
    # Always includes: safety constraints, spec files, core config
```

Any write attempt to a protected path is blocked at the filesystem level, not at the prompt level.

#### Rollback Registry

```python
class RollbackRegistry:
    """Every modification is reversible."""
    def record_modification(self, path: str, before: bytes, after: bytes) -> str
    def rollback(self, modification_id: str) -> None
    def rollback_all_since(self, timestamp: datetime) -> int
```

Modifications without a rollback record are rejected.

## Improvement Lifecycle

1. **Observation** — Agent identifies a pattern from execution traces
2. **Proposal** — Agent formulates a specific improvement (new skill, config change, workflow adjustment)
3. **Validation** — Proposal is checked against safety constraints
4. **Application** — If valid, modification is applied with rollback record
5. **Evaluation** — Improvement is monitored for effectiveness
6. **Retention or Rollback** — Keep if effective, rollback if degrading

### What Can Be Improved

| Category | Example | Constraint |
|----------|---------|-----------|
| Skills | New capability from execution patterns | Must pass all four quality gates |
| Preferences | Learned user corrections | Must not contradict protected preferences |
| Workflows | Optimized task sequences | Must not bypass coordination protocol |
| Knowledge | New facts from experience | Must pass memory governance validation |

### What Cannot Be Improved (Immutable)

| Category | Reason |
|----------|--------|
| Safety constraints themselves | Prevents constraint erosion |
| Spec files | Architecture is fixed by design |
| Core identity/role | Prevents goal drift |
| Trust tier promotion rules | Prevents trust inflation |
| Rate limiter configuration | Prevents unbounded modification |

## Threat Model

SHARD's self-improvement constraints defend against **degradation from poor optimization**, not adversarial attacks:

| Threat | Defense |
|--------|---------|
| Capability drift | Rate limiting + evaluation period before retention |
| Memory pollution | Memory governance validates all new knowledge |
| Coordination decay | Self-modifications are declared as intents |
| Unbounded modification | Hard rate limits + scope guards |
| Constraint erosion | Protected paths are immutable by the agent |

## Interfaces

### Read Interface

```python
class SelfImprovementRead:
    def get_modification_count(self, window: timedelta) -> int
    def get_modification_history(self, limit: int) -> list[Modification]
    def is_within_bounds(self) -> bool
    def get_protected_paths(self) -> list[str]
```

### Write Interface

```python
class SelfImprovementWrite:
    def propose(self, proposal: ImprovementProposal) -> ProposalResult
    def rollback(self, modification_id: str) -> None
    def evaluate(self, modification_id: str) -> EvaluationResult
```

## Integration Points

| Subsystem | Interaction |
|-----------|-------------|
| Memory Governance | New learnings validated before storage |
| Coordination | Self-modification intents are declared and reviewed |
| Skill Lifecycle | Self-generated skills enter at T1, must pass all gates |
| Safety (self) | Constraints are checked before every modification; protected paths enforced at write time |
