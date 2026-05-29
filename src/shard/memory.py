"""Memory Governance — staleness detection, 3D validation, conflict resolution.

This module governs the quality of agent memory. It does not store memories
(the gateway does that). It validates, detects staleness, resolves conflicts,
and propagates invalidation through dependency chains.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ValidationDimension(Enum):
    TEMPORAL = "temporal"
    SEMANTIC = "semantic"
    STRUCTURAL = "structural"


class StaleTrigger(Enum):
    TIME_BASED = "time_based"
    DEPENDENCY = "dependency"
    CONTRADICTION = "contradiction"
    EXTERNAL = "external"


class ConflictStrategy(Enum):
    RECENCY = "recency"
    SOURCE_AUTHORITY = "source_authority"
    SPECIFICITY = "specificity"
    MANUAL = "manual"


@dataclass
class Memory:
    id: str
    content: str
    created_at: float = field(default_factory=time.time)
    last_verified: float = field(default_factory=time.time)
    ttl_seconds: float = 86400 * 30  # 30 days default
    source: str = "agent"
    source_authority: int = 0  # higher = more authoritative
    specificity: int = 0  # higher = more specific
    depends_on: list[str] = field(default_factory=list)
    schema: Optional[dict] = None  # expected structure for structural validation
    valid: bool = True
    invalidation_reason: Optional[str] = None


@dataclass
class ValidationResult:
    valid: bool
    dimensions: dict[ValidationDimension, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class ConflictRecord:
    memory_a: str
    memory_b: str
    description: str
    resolved: bool = False
    winner: Optional[str] = None
    strategy_used: Optional[ConflictStrategy] = None


class MemoryGovernance:
    """Full memory governance: staleness, validation, conflict resolution, cascades."""

    def __init__(
        self,
        max_cascade_depth: int = 5,
        default_conflict_strategy: ConflictStrategy = ConflictStrategy.RECENCY,
    ):
        self._memories: dict[str, Memory] = {}
        self._conflicts: list[ConflictRecord] = []
        self._max_cascade_depth = max_cascade_depth
        self._default_strategy = default_conflict_strategy

    # ─── Storage ───────────────────────────────────────────────

    def store(self, memory: Memory) -> None:
        """Store a memory under governance."""
        self._memories[memory.id] = memory

    def get(self, memory_id: str) -> Optional[Memory]:
        return self._memories.get(memory_id)

    # ─── Read Interface ────────────────────────────────────────

    def is_valid(self, memory_id: str) -> ValidationResult:
        """Full 3D validation of a memory."""
        memory = self._memories.get(memory_id)
        if memory is None:
            return ValidationResult(valid=False, reasons=["Memory not found"])

        if not memory.valid:
            return ValidationResult(valid=False, reasons=[memory.invalidation_reason or "Previously invalidated"])

        dimensions = {
            ValidationDimension.TEMPORAL: self._validate_temporal(memory),
            ValidationDimension.SEMANTIC: self._validate_semantic(memory),
            ValidationDimension.STRUCTURAL: self._validate_structural(memory),
        }

        reasons = []
        if not dimensions[ValidationDimension.TEMPORAL]:
            reasons.append(f"Stale: exceeded TTL ({memory.ttl_seconds}s)")
        if not dimensions[ValidationDimension.SEMANTIC]:
            reasons.append("Conflicts with other valid memories")
        if not dimensions[ValidationDimension.STRUCTURAL]:
            reasons.append("Fails structural schema validation")

        return ValidationResult(
            valid=all(dimensions.values()),
            dimensions=dimensions,
            reasons=reasons,
        )

    def get_staleness_score(self, memory_id: str) -> float:
        """0.0 = fresh, 1.0 = stale (at or beyond TTL)."""
        memory = self._memories.get(memory_id)
        if memory is None:
            return 1.0
        elapsed = time.time() - memory.last_verified
        return min(1.0, elapsed / memory.ttl_seconds)

    def get_conflicts(self, memory_id: str) -> list[ConflictRecord]:
        """Get all conflict records involving this memory."""
        return [
            c for c in self._conflicts
            if c.memory_a == memory_id or c.memory_b == memory_id
        ]

    def get_dependency_chain(self, memory_id: str) -> list[str]:
        """Get all memories that depend on this one (direct + transitive)."""
        dependents: list[str] = []
        self._collect_dependents(memory_id, dependents, depth=0)
        return dependents

    # ─── Write Interface ───────────────────────────────────────

    def report_stale(self, memory_id: str, evidence: str) -> None:
        """External signal that a memory is stale."""
        memory = self._memories.get(memory_id)
        if memory:
            self.invalidate(memory_id, f"External stale report: {evidence}")

    def report_conflict(self, memory_a: str, memory_b: str, description: str) -> ConflictRecord:
        """Report a conflict between two memories. Attempts resolution."""
        record = ConflictRecord(memory_a=memory_a, memory_b=memory_b, description=description)
        self._conflicts.append(record)
        self._resolve_conflict(record)
        return record

    def invalidate(self, memory_id: str, reason: str) -> list[str]:
        """Invalidate a memory and cascade to dependents. Returns all invalidated IDs."""
        return self._cascade_invalidate(memory_id, reason, depth=0)

    def refresh(self, memory_id: str, new_evidence: str) -> None:
        """Mark a memory as freshly verified."""
        memory = self._memories.get(memory_id)
        if memory:
            memory.last_verified = time.time()
            memory.valid = True
            memory.invalidation_reason = None

    # ─── 3D Validation ─────────────────────────────────────────

    def _validate_temporal(self, memory: Memory) -> bool:
        """Is this memory still within its TTL?"""
        elapsed = time.time() - memory.last_verified
        return elapsed < memory.ttl_seconds

    def _validate_semantic(self, memory: Memory) -> bool:
        """Does this memory conflict with other valid memories?"""
        unresolved = [
            c for c in self._conflicts
            if (c.memory_a == memory.id or c.memory_b == memory.id)
            and not c.resolved
        ]
        return len(unresolved) == 0

    def _validate_structural(self, memory: Memory) -> bool:
        """Does this memory conform to its declared schema?"""
        if memory.schema is None:
            return True  # No schema = no structural requirement

        # Check required fields exist in content
        required = memory.schema.get("required_fields", [])
        for req_field in required:
            if req_field not in memory.content:
                return False
        return True

    # ─── Staleness Cascade ─────────────────────────────────────

    def _cascade_invalidate(self, memory_id: str, reason: str, depth: int) -> list[str]:
        """Invalidate and propagate through dependency graph."""
        if depth >= self._max_cascade_depth:
            return []

        memory = self._memories.get(memory_id)
        if memory is None or not memory.valid:
            return []

        memory.valid = False
        memory.invalidation_reason = reason
        invalidated = [memory_id]

        # Find all memories that depend on this one
        for mid, m in self._memories.items():
            if memory_id in m.depends_on and m.valid:
                cascade_reason = f"Dependency invalidated: {memory_id} ({reason})"
                invalidated.extend(
                    self._cascade_invalidate(mid, cascade_reason, depth + 1)
                )

        return invalidated

    def _collect_dependents(self, memory_id: str, result: list[str], depth: int) -> None:
        """Collect transitive dependents (breadth-first)."""
        if depth >= self._max_cascade_depth:
            return
        for mid, m in self._memories.items():
            if memory_id in m.depends_on and mid not in result:
                result.append(mid)
                self._collect_dependents(mid, result, depth + 1)

    # ─── Conflict Resolution ───────────────────────────────────

    def _resolve_conflict(self, record: ConflictRecord) -> None:
        """Attempt to resolve a conflict using configured strategy."""
        a = self._memories.get(record.memory_a)
        b = self._memories.get(record.memory_b)

        if a is None or b is None:
            return

        strategy = self._default_strategy
        winner = None

        if strategy == ConflictStrategy.RECENCY:
            winner = record.memory_a if a.last_verified >= b.last_verified else record.memory_b

        elif strategy == ConflictStrategy.SOURCE_AUTHORITY:
            winner = record.memory_a if a.source_authority >= b.source_authority else record.memory_b

        elif strategy == ConflictStrategy.SPECIFICITY:
            winner = record.memory_a if a.specificity >= b.specificity else record.memory_b

        elif strategy == ConflictStrategy.MANUAL:
            # Cannot auto-resolve — leave unresolved for human
            return

        if winner:
            record.resolved = True
            record.winner = winner
            record.strategy_used = strategy
            # Invalidate the loser
            loser = record.memory_b if winner == record.memory_a else record.memory_a
            loser_mem = self._memories.get(loser)
            if loser_mem:
                loser_mem.valid = False
                loser_mem.invalidation_reason = f"Conflict resolved: lost to {winner} via {strategy.value}"
