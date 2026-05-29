"""Tests for safety constraints (rate limiter, scope guard, rollback registry)."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from shard.safety import RateLimiter, RateLimiterConfig, RollbackRegistry, ScopeGuard


class TestRateLimiter:
    def _make_limiter(self, tmp_path, **kwargs):
        config = RateLimiterConfig(**kwargs)
        return RateLimiter(tmp_path / "rate_state.json", config)

    def test_allows_within_limit(self, tmp_path):
        limiter = self._make_limiter(tmp_path, max_per_session=3)
        assert limiter.allow() is True

    def test_blocks_at_session_limit(self, tmp_path):
        limiter = self._make_limiter(tmp_path, max_per_session=2)
        limiter.record(success=True)
        limiter.record(success=True)
        assert limiter.allow() is False

    def test_blocks_during_cooldown(self, tmp_path):
        limiter = self._make_limiter(tmp_path, cooldown_after_failure_seconds=3600)
        limiter.record(success=False)
        assert limiter.allow() is False

    def test_persists_across_instances(self, tmp_path):
        state_path = tmp_path / "rate_state.json"
        config = RateLimiterConfig(max_per_session=5, max_per_day=3)

        limiter1 = RateLimiter(state_path, config)
        limiter1.record(success=True)
        limiter1.record(success=True)
        limiter1.record(success=True)

        # New instance reads persisted state
        limiter2 = RateLimiter(state_path, config)
        assert limiter2.allow() is False  # day limit hit

    def test_session_reset_clears_session_count(self, tmp_path):
        limiter = self._make_limiter(tmp_path, max_per_session=2, max_per_day=100)
        limiter.record(success=True)
        limiter.record(success=True)
        assert limiter.allow() is False
        limiter.reset_session()
        assert limiter.allow() is True


class TestScopeGuard:
    def test_blocks_protected_path(self):
        guard = ScopeGuard(["/etc/shard/constraints"])
        assert guard.is_protected("/etc/shard/constraints/rules.yaml") is True

    def test_allows_unprotected_path(self):
        guard = ScopeGuard(["/etc/shard/constraints"])
        assert guard.is_protected("/home/user/workspace/file.py") is False

    def test_blocks_exact_protected_path(self):
        guard = ScopeGuard(["/etc/shard/config.json"])
        assert guard.is_protected("/etc/shard/config.json") is True

    def test_check_write_raises(self):
        guard = ScopeGuard(["/protected"])
        with pytest.raises(PermissionError):
            guard.check_write("/protected/secret.key")

    def test_check_write_passes(self):
        guard = ScopeGuard(["/protected"])
        guard.check_write("/allowed/file.txt")  # Should not raise


class TestRollbackRegistry:
    def test_record_and_rollback(self, tmp_path):
        registry = RollbackRegistry(tmp_path / "rollbacks.json")
        target = tmp_path / "target.txt"
        target.write_text("original")

        registry.record("mod-1", str(target), "original", "modified")
        target.write_text("modified")

        restored = registry.rollback("mod-1")
        assert restored == "original"
        assert target.read_text() == "original"

    def test_rollback_nonexistent_returns_none(self, tmp_path):
        registry = RollbackRegistry(tmp_path / "rollbacks.json")
        assert registry.rollback("nonexistent") is None

    def test_rollback_all_since(self, tmp_path):
        registry = RollbackRegistry(tmp_path / "rollbacks.json")
        f1 = tmp_path / "f1.txt"
        f2 = tmp_path / "f2.txt"
        f1.write_text("orig1")
        f2.write_text("orig2")

        before = time.time()
        registry.record("m1", str(f1), "orig1", "new1")
        registry.record("m2", str(f2), "orig2", "new2")
        f1.write_text("new1")
        f2.write_text("new2")

        count = registry.rollback_all_since(before)
        assert count == 2
        assert f1.read_text() == "orig1"
        assert f2.read_text() == "orig2"
