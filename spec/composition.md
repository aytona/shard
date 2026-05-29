# Composition Specification

## Purpose

Define how SHARD's four subsystems interact through typed interfaces to produce emergent properties — behaviors that no individual subsystem was designed to provide.

## The Composition Principle

Each subsystem is independently motivated and contextually activated. No subsystem "knows" the full architecture. Coherent system behavior is a property of their interaction, not of any central design.

This means:
- Removing any one subsystem degrades the whole (not just that subsystem's function)
- Adding a subsystem improves the whole beyond that subsystem's individual contribution
- The system's most valuable properties exist only at the composition level

## Composition Interfaces

A composition interface is a **typed read/write protocol** between two subsystems. It defines:
- What data flows between them
- What format that data takes
- What guarantees each side provides

### Interface Map

```
Memory Governance ←→ Skill Lifecycle
    Reads: dependency validity for skills
    Writes: skill demotion triggers on staleness

Memory Governance ←→ Coordination
    Reads: (none)
    Writes: memory invalidation as declared intent

Memory Governance ←→ Self-Improvement
    Reads: (none)
    Writes: validation results for proposed new knowledge

Skill Lifecycle ←→ Coordination
    Reads: (none)
    Writes: capability changes as declared intents

Skill Lifecycle ←→ Self-Improvement
    Reads: gate results for self-generated skills
    Writes: (self-generated skills submitted as candidates)

Coordination ←→ Self-Improvement
    Reads: active intents (to avoid conflicting modifications)
    Writes: self-modification as declared intent

Safety ←→ All
    Reads: constraint checks before any modification
    Writes: violation reports, blocked action logs
```

## Compositional Fault Recovery

The primary emergent property. When a fault occurs, the composition enables recovery paths that span multiple subsystems:

### Example: Stale Dependency Cascade

1. **Memory Governance** detects a memory has become stale
2. **Skill Lifecycle** is notified → checks which skills depend on that memory → demotes affected skills
3. **Coordination** receives the demotion as a declared intent → broadcasts to other agents
4. **Self-Improvement** notes the pattern → proposes adding a staleness check to prevent recurrence
5. **Safety** validates the proposed improvement → allows it (within bounds)

No single subsystem "designed" this recovery. Each responded to its own inputs through its own logic. The recovery emerged from composition.

### Example: Conflicting Self-Improvement

1. **Self-Improvement** proposes a modification
2. **Coordination** checks active intents → finds a conflict with another agent's declared work
3. **Self-Improvement** receives CONFLICT → backs off
4. **Memory Governance** records the conflict for future reference
5. Next attempt: **Self-Improvement** checks memory first → avoids the same conflict

### Example: Untrusted Skill Invocation

1. **Skill Lifecycle** receives an invocation request for a T1 (sandboxed) skill
2. **Safety** checks invocation count → within bounds → allows
3. Skill executes → produces unexpected output
4. **Skill Lifecycle** records failure → increments failure counter
5. **Memory Governance** validates the failure record → confirms it's not a stale test case
6. After threshold: **Skill Lifecycle** demotes to retired → **Coordination** broadcasts

## Ablation Properties

Removing subsystems demonstrates composition value:

| Configuration | Behavior | Failure Mode |
|--------------|----------|--------------|
| Full SHARD (all 4) | Compositional fault recovery | — |
| Without Memory Governance | Skills operate on stale data, no cascade detection | Silent degradation |
| Without Coordination | Agents conflict, self-improvement collides | Resource corruption |
| Without Skill Lifecycle | Capabilities accumulate without quality control | Capability pollution |
| Without Safety | Self-improvement is unbounded | Constraint erosion, drift |
| Any single subsystem alone | Individual function only, no recovery | 1/5 composition tests pass |

## Design Constraints

- **No subsystem may depend on the internal state of another** — only on its read interface
- **Interfaces are the contract** — implementations can vary across gateways
- **Graceful degradation** — if a subsystem is unavailable, others continue (with reduced capability, not failure)
- **No circular blocking** — interface calls are non-blocking; results are eventually consistent
