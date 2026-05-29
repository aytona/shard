"""Tests for coordination protocol — DECLARE, REVIEW, EXECUTE phases."""

import time

import pytest

from shard.coordination import (
    ActionResult,
    ActionStatus,
    ConflictResolution,
    CoordinationProtocol,
    Intent,
    ReviewResult,
)


class TestDeclarePhase:
    def test_declare_returns_intent_id(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="file.txt", rationale="update")
        iid = proto.declare(intent)
        assert iid == intent.id
        assert proto.get_intent(iid).status == ActionStatus.DECLARED

    def test_withdraw_declared_intent(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="file.txt", rationale="update")
        iid = proto.declare(intent)
        assert proto.withdraw(iid) is True
        assert proto.get_intent(iid) is None  # Archived

    def test_withdraw_executing_intent_fails(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="file.txt", rationale="update")
        iid = proto.declare(intent)
        proto.begin_execution(iid)
        assert proto.withdraw(iid) is False

    def test_expired_intents_pruned(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="f.txt", rationale="x", ttl_seconds=0.01)
        intent.timestamp = time.time() - 1  # Already expired
        proto.declare(intent)
        active = proto.get_active_intents()
        assert len(active) == 0


class TestReviewPhase:
    def test_no_conflict_returns_clear(self):
        proto = CoordinationProtocol()
        i1 = Intent(agent_id="a1", action="write", target="file_a.txt", rationale="update a")
        i2 = Intent(agent_id="a2", action="write", target="file_b.txt", rationale="update b")
        proto.declare(i1)
        proto.declare(i2)
        result, conflicts = proto.review(i2.id)
        assert result == ReviewResult.CLEAR
        assert conflicts == []

    def test_same_target_different_action_is_syntactic_conflict(self):
        proto = CoordinationProtocol()
        i1 = Intent(agent_id="a1", action="write", target="shared.txt", rationale="update")
        i2 = Intent(agent_id="a2", action="delete", target="shared.txt", rationale="cleanup")
        proto.declare(i1)
        proto.declare(i2)
        result, conflicts = proto.review(i2.id)
        assert result == ReviewResult.CONFLICT
        assert conflicts[0].conflict_type == "syntactic"

    def test_same_target_same_action_is_duplicate(self):
        proto = CoordinationProtocol()
        i1 = Intent(agent_id="a1", action="write", target="shared.txt", rationale="update")
        i2 = Intent(agent_id="a2", action="write", target="shared.txt", rationale="also update")
        proto.declare(i1)
        proto.declare(i2)
        result, conflicts = proto.review(i2.id)
        assert result == ReviewResult.DUPLICATE

    def test_withdrawn_intents_dont_conflict(self):
        proto = CoordinationProtocol()
        i1 = Intent(agent_id="a1", action="write", target="shared.txt", rationale="x")
        i2 = Intent(agent_id="a2", action="delete", target="shared.txt", rationale="y")
        proto.declare(i1)
        proto.withdraw(i1.id)
        proto.declare(i2)
        result, _ = proto.review(i2.id)
        assert result == ReviewResult.CLEAR


class TestConflictResolution:
    def test_first_declared_wins(self):
        proto = CoordinationProtocol(resolution_strategy=ConflictResolution.FIRST_DECLARED)
        i1 = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        i1.timestamp = time.time() - 10  # Declared earlier
        i2 = Intent(agent_id="a2", action="delete", target="f.txt", rationale="y")
        proto.declare(i1)
        proto.declare(i2)
        _, conflicts = proto.review(i2.id)
        can_proceed = proto.resolve(i2.id, conflicts)
        assert can_proceed is False
        assert proto.get_intent(i2.id).status == ActionStatus.BLOCKED

    def test_priority_wins(self):
        proto = CoordinationProtocol(resolution_strategy=ConflictResolution.PRIORITY)
        i1 = Intent(agent_id="a1", action="write", target="f.txt", rationale="x", priority=1)
        i2 = Intent(agent_id="a2", action="delete", target="f.txt", rationale="y", priority=10)
        proto.declare(i1)
        proto.declare(i2)
        _, conflicts = proto.review(i2.id)
        can_proceed = proto.resolve(i2.id, conflicts)
        assert can_proceed is True  # Higher priority wins

    def test_merge_allows_both(self):
        proto = CoordinationProtocol(resolution_strategy=ConflictResolution.MERGE)
        i1 = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        i2 = Intent(agent_id="a2", action="write", target="f.txt", rationale="y")
        proto.declare(i1)
        proto.declare(i2)
        _, conflicts = proto.review(i2.id)
        can_proceed = proto.resolve(i2.id, conflicts)
        assert can_proceed is True

    def test_escalate_always_blocks(self):
        proto = CoordinationProtocol(resolution_strategy=ConflictResolution.ESCALATE)
        i1 = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        i2 = Intent(agent_id="a2", action="delete", target="f.txt", rationale="y")
        proto.declare(i1)
        proto.declare(i2)
        _, conflicts = proto.review(i2.id)
        can_proceed = proto.resolve(i2.id, conflicts)
        assert can_proceed is False


class TestExecutePhase:
    def test_begin_execution_from_declared(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        proto.declare(intent)
        assert proto.begin_execution(intent.id) is True
        assert proto.get_intent(intent.id).status == ActionStatus.EXECUTING

    def test_begin_execution_from_blocked_fails(self):
        proto = CoordinationProtocol(resolution_strategy=ConflictResolution.ESCALATE)
        i1 = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        i2 = Intent(agent_id="a2", action="delete", target="f.txt", rationale="y")
        proto.declare(i1)
        proto.declare(i2)
        _, conflicts = proto.review(i2.id)
        proto.resolve(i2.id, conflicts)  # Blocks i2
        assert proto.begin_execution(i2.id) is False

    def test_report_completion_success(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        proto.declare(intent)
        proto.begin_execution(intent.id)
        proto.report_completion(intent.id, ActionResult(intent_id=intent.id, success=True))
        # Should be archived now
        assert proto.get_intent(intent.id) is None
        assert len(proto.get_history()) == 1

    def test_report_completion_failure(self):
        proto = CoordinationProtocol()
        intent = Intent(agent_id="a1", action="write", target="f.txt", rationale="x")
        proto.declare(intent)
        proto.begin_execution(intent.id)
        proto.report_completion(intent.id, ActionResult(intent_id=intent.id, success=False, error="disk full"))
        history = proto.get_history()
        assert history[-1].status == ActionStatus.FAILED


class TestQueryInterface:
    def test_get_intents_for_target(self):
        proto = CoordinationProtocol()
        proto.declare(Intent(agent_id="a1", action="read", target="shared.txt", rationale="x"))
        proto.declare(Intent(agent_id="a2", action="write", target="shared.txt", rationale="y"))
        proto.declare(Intent(agent_id="a3", action="write", target="other.txt", rationale="z"))
        results = proto.get_intents_for_target("shared.txt")
        assert len(results) == 2

    def test_get_agent_intents(self):
        proto = CoordinationProtocol()
        proto.declare(Intent(agent_id="a1", action="read", target="f1.txt", rationale="x"))
        proto.declare(Intent(agent_id="a1", action="write", target="f2.txt", rationale="y"))
        proto.declare(Intent(agent_id="a2", action="write", target="f3.txt", rationale="z"))
        results = proto.get_agent_intents("a1")
        assert len(results) == 2
