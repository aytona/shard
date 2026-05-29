"""Quickstart example — demonstrates SHARD composition in action."""

from pathlib import Path
from shard.composition import SHARD
from shard.memory import Memory
from shard.safety import RateLimiter, RateLimiterConfig, ScopeGuard, RollbackRegistry
from shard.skills import SkillCandidate, InvocationResult


def main():
    # Initialize SHARD with all subsystems composed
    shard = SHARD(
        rate_limiter=RateLimiter(
            Path("/tmp/shard_rate_state.json"),
            RateLimiterConfig(max_per_session=5, max_per_day=20),
        ),
        scope_guard=ScopeGuard(["system-config", "safety-rules"]),
        rollback=RollbackRegistry(Path("/tmp/shard_rollbacks.json")),
    )

    # 1. Store governed memories
    print("=== Memory Governance ===")
    shard.governed_memory_store(Memory(id="api-url", content="https://api.example.com/v2"))
    shard.governed_memory_store(Memory(id="user-pref", content="timezone: America/Toronto"))
    print(f"Stored 2 memories. Staleness score: {shard.memory.get_staleness_score('api-url'):.2f}")

    # 2. Submit skills through quality gates
    print("\n=== Skill Lifecycle ===")
    result, skill_id = shard.governed_skill_submit(
        SkillCandidate(
            name="data-fetcher",
            description="fetches data from configured API endpoint",
            source="human",
            test_cases=[{"expected": 200, "actual": 200}],
            metadata={"memory_dependencies": ["api-url"]},
        )
    )
    print(f"Skill submission: {result}, id: {skill_id}")

    # 3. Invoke the skill (with coordination)
    print("\n=== Coordinated Invocation ===")
    success = shard.governed_skill_invoke(skill_id)
    print(f"Invocation success: {success}")

    # 4. Simulate fault recovery: memory goes stale
    print("\n=== Compositional Fault Recovery ===")
    print("Simulating: API endpoint has moved...")
    invalidated = shard.handle_stale_memory("api-url", "endpoint migrated to v3")
    print(f"Invalidated {len(invalidated)} memories")
    print(f"Skill trust tier after cascade: {shard.skills.get_skill(skill_id).trust_tier.name}")

    # 5. Observe composition events
    print("\n=== Composition Events ===")
    for event in shard.get_events():
        print(f"  [{event.source} → {event.target}] {event.action}: {event.detail}")


if __name__ == "__main__":
    main()
