"""Tests for memory governance — staleness, 3D validation, conflicts, cascades."""

import time

import pytest

from shard.memory import (
    ConflictStrategy,
    Memory,
    MemoryGovernance,
    StaleTrigger,
    ValidationDimension,
)


class TestStalenessDetection:
    def test_fresh_memory_is_valid(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="m1", content="fact", ttl_seconds=3600))
        result = gov.is_valid("m1")
        assert result.valid is True
        assert result.dimensions[ValidationDimension.TEMPORAL] is True

    def test_expired_memory_is_stale(self):
        gov = MemoryGovernance()
        mem = Memory(id="m1", content="old fact", ttl_seconds=1)
        mem.last_verified = time.time() - 10  # Expired 9 seconds ago
        gov.store(mem)
        result = gov.is_valid("m1")
        assert result.valid is False
        assert result.dimensions[ValidationDimension.TEMPORAL] is False

    def test_staleness_score_fresh(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="m1", content="fact", ttl_seconds=3600))
        score = gov.get_staleness_score("m1")
        assert score < 0.01  # Nearly fresh

    def test_staleness_score_expired(self):
        gov = MemoryGovernance()
        mem = Memory(id="m1", content="fact", ttl_seconds=100)
        mem.last_verified = time.time() - 200  # 2x TTL
        gov.store(mem)
        score = gov.get_staleness_score("m1")
        assert score == 1.0  # Capped at 1.0

    def test_staleness_score_nonexistent(self):
        gov = MemoryGovernance()
        assert gov.get_staleness_score("nope") == 1.0

    def test_refresh_resets_staleness(self):
        gov = MemoryGovernance()
        mem = Memory(id="m1", content="fact", ttl_seconds=1)
        mem.last_verified = time.time() - 10
        gov.store(mem)
        assert gov.is_valid("m1").valid is False
        gov.refresh("m1", "re-verified")
        assert gov.is_valid("m1").valid is True


class TestDependencyCascade:
    def test_invalidation_cascades_to_dependents(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="root", content="base fact"))
        gov.store(Memory(id="child", content="derived", depends_on=["root"]))
        gov.store(Memory(id="grandchild", content="further derived", depends_on=["child"]))

        invalidated = gov.invalidate("root", "outdated")
        assert "root" in invalidated
        assert "child" in invalidated
        assert "grandchild" in invalidated

    def test_cascade_stops_at_max_depth(self):
        gov = MemoryGovernance(max_cascade_depth=2)
        gov.store(Memory(id="a", content="a"))
        gov.store(Memory(id="b", content="b", depends_on=["a"]))
        gov.store(Memory(id="c", content="c", depends_on=["b"]))
        gov.store(Memory(id="d", content="d", depends_on=["c"]))  # depth 3 — should not cascade

        invalidated = gov.invalidate("a", "stale")
        assert "a" in invalidated
        assert "b" in invalidated
        assert "c" not in invalidated  # Beyond max depth
        assert "d" not in invalidated

    def test_cascade_does_not_revisit_already_invalid(self):
        gov = MemoryGovernance()
        mem = Memory(id="already_dead", content="x", depends_on=["root"])
        mem.valid = False
        gov.store(Memory(id="root", content="root"))
        gov.store(mem)

        invalidated = gov.invalidate("root", "stale")
        assert "already_dead" not in invalidated

    def test_get_dependency_chain(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="a", content="a"))
        gov.store(Memory(id="b", content="b", depends_on=["a"]))
        gov.store(Memory(id="c", content="c", depends_on=["b"]))
        gov.store(Memory(id="unrelated", content="x"))

        chain = gov.get_dependency_chain("a")
        assert "b" in chain
        assert "c" in chain
        assert "unrelated" not in chain


class TestConflictResolution:
    def test_recency_strategy(self):
        gov = MemoryGovernance(default_conflict_strategy=ConflictStrategy.RECENCY)
        old = Memory(id="old", content="earth is flat")
        old.last_verified = time.time() - 1000
        new = Memory(id="new", content="earth is round")
        gov.store(old)
        gov.store(new)

        record = gov.report_conflict("old", "new", "shape of earth")
        assert record.resolved is True
        assert record.winner == "new"
        assert gov.get("old").valid is False

    def test_source_authority_strategy(self):
        gov = MemoryGovernance(default_conflict_strategy=ConflictStrategy.SOURCE_AUTHORITY)
        low = Memory(id="low", content="maybe", source_authority=1)
        high = Memory(id="high", content="definitely", source_authority=10)
        gov.store(low)
        gov.store(high)

        record = gov.report_conflict("low", "high", "certainty")
        assert record.winner == "high"
        assert gov.get("low").valid is False

    def test_specificity_strategy(self):
        gov = MemoryGovernance(default_conflict_strategy=ConflictStrategy.SPECIFICITY)
        general = Memory(id="gen", content="animals have legs", specificity=1)
        specific = Memory(id="spec", content="snakes have no legs", specificity=5)
        gov.store(general)
        gov.store(specific)

        record = gov.report_conflict("gen", "spec", "legs")
        assert record.winner == "spec"

    def test_manual_strategy_leaves_unresolved(self):
        gov = MemoryGovernance(default_conflict_strategy=ConflictStrategy.MANUAL)
        gov.store(Memory(id="a", content="x"))
        gov.store(Memory(id="b", content="y"))

        record = gov.report_conflict("a", "b", "disagreement")
        assert record.resolved is False
        assert record.winner is None

    def test_unresolved_conflict_fails_semantic_validation(self):
        gov = MemoryGovernance(default_conflict_strategy=ConflictStrategy.MANUAL)
        gov.store(Memory(id="a", content="x"))
        gov.store(Memory(id="b", content="y"))
        gov.report_conflict("a", "b", "disagreement")

        result = gov.is_valid("a")
        assert result.dimensions[ValidationDimension.SEMANTIC] is False


class TestStructuralValidation:
    def test_no_schema_passes(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="m1", content="anything"))
        result = gov.is_valid("m1")
        assert result.dimensions[ValidationDimension.STRUCTURAL] is True

    def test_schema_with_required_fields_passes(self):
        gov = MemoryGovernance()
        gov.store(Memory(
            id="m1",
            content="name: Chris, role: DA",
            schema={"required_fields": ["name", "role"]},
        ))
        result = gov.is_valid("m1")
        assert result.dimensions[ValidationDimension.STRUCTURAL] is True

    def test_schema_with_missing_field_fails(self):
        gov = MemoryGovernance()
        gov.store(Memory(
            id="m1",
            content="name: Chris",
            schema={"required_fields": ["name", "role"]},
        ))
        result = gov.is_valid("m1")
        assert result.dimensions[ValidationDimension.STRUCTURAL] is False


class TestExternalSignals:
    def test_report_stale_invalidates(self):
        gov = MemoryGovernance()
        gov.store(Memory(id="m1", content="fact"))
        gov.report_stale("m1", "user said this is wrong")
        assert gov.get("m1").valid is False

    def test_nonexistent_memory_validation(self):
        gov = MemoryGovernance()
        result = gov.is_valid("ghost")
        assert result.valid is False
        assert "not found" in result.reasons[0].lower()
