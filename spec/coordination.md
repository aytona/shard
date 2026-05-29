# Intent-Based Coordination Specification

## Purpose

Enable multiple agents to operate in a shared environment without semantic conflicts, using a lightweight declaration protocol rather than a central orchestrator.

## Problem Statement

Uncoordinated multi-agent systems produce:
- **Resource conflicts** — Two agents modifying the same artifact simultaneously
- **Semantic contradictions** — Agents pursuing incompatible goals on the same target
- **Redundant work** — Multiple agents solving the same problem independently
- **Cascade failures** — One agent's action invalidating another's in-progress work

## The DECLARE→REVIEW→EXECUTE Protocol

### Phase 1: DECLARE

Before taking any action that modifies shared state, an agent broadcasts its intent:

```python
@dataclass
class Intent:
    agent_id: str
    action: str           # What the agent plans to do
    target: str           # What resource/artifact is affected
    rationale: str        # Why (enables semantic conflict detection)
    timestamp: datetime
    ttl: timedelta        # How long this declaration is valid
```

Declaration is non-blocking. The agent does not wait for approval — it proceeds to review.

### Phase 2: REVIEW

The coordination system (and optionally other agents) evaluates the declared intent:

```python
class ReviewResult:
    CLEAR = "clear"           # No conflicts detected
    CONFLICT = "conflict"     # Semantic conflict with another intent
    DUPLICATE = "duplicate"   # Another agent already declared equivalent intent
    SUPERSEDED = "superseded" # A higher-priority intent covers this
```

**Conflict detection levels:**
| Level | Detection | Example |
|-------|-----------|---------|
| Syntactic | Same target resource | Two agents editing the same file |
| Semantic | Incompatible goals on related resources | One agent adding a dependency another is removing |
| Transitive | Conflict through dependency chain | Agent A modifies X, Agent B depends on X for Y |

### Phase 3: EXECUTE

- If CLEAR → proceed with action
- If CONFLICT → resolve (strategies below) or abort
- If DUPLICATE → yield to the other agent (or negotiate)
- If SUPERSEDED → abort

## Conflict Resolution Strategies

| Strategy | When to use |
|----------|-------------|
| Priority-based | Agents have assigned priority levels |
| First-declared | Earlier declaration wins |
| Merge | Both intents can be satisfied with a combined action |
| Escalate | Flag for human/supervisor resolution |
| Retry-later | Back off and re-declare after TTL expires |

## Interfaces

### Read Interface

```python
class CoordinationRead:
    def get_active_intents(self) -> list[Intent]
    def get_conflicts_for(self, intent: Intent) -> list[ReviewResult]
    def get_agent_status(self, agent_id: str) -> AgentStatus
```

### Write Interface

```python
class CoordinationWrite:
    def declare(self, intent: Intent) -> str  # Returns intent_id
    def withdraw(self, intent_id: str) -> None
    def report_completion(self, intent_id: str, result: ActionResult) -> None
    def report_failure(self, intent_id: str, error: str) -> None
```

## Properties

- **No central orchestrator** — Coordination emerges from the protocol, not from a decision-maker
- **Non-blocking by default** — Declaration doesn't pause the agent; review happens concurrently
- **Graceful degradation** — If coordination is unavailable, agents fall back to uncoordinated operation (with logged warnings)
- **Bounded** — Intents expire via TTL; stale declarations are automatically cleared

## Integration Points

| Subsystem | Interaction |
|-----------|-------------|
| Memory Governance | Memory invalidation is declared as an intent (other agents may cache affected data) |
| Skill Lifecycle | Skill promotion/demotion is declared (other agents may depend on the capability) |
| Self-Improvement | Self-modification intents are declared and reviewed before execution |
