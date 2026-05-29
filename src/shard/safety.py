"""Safety constraints — programmatic enforcement for self-improvement bounds.

This module implements the hard guards that prevent unbounded self-modification:
- Rate limiting (max modifications per window)
- Scope guards (immutable paths)
- Rollback registry (every change is reversible)

These are code, not prompts. An agent cannot reason its way around them.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RateLimiterConfig:
    max_per_session: int = 5
    max_per_day: int = 20
    cooldown_after_failure_seconds: int = 3600


class RateLimiter:
    """Hard cap on modifications per time window. Persists across sessions."""

    def __init__(self, state_path: Path, config: Optional[RateLimiterConfig] = None):
        self._state_path = state_path
        self._config = config or RateLimiterConfig()
        self._state = self._load_state()

    def allow(self) -> bool:
        """Check if a modification is permitted right now."""
        now = time.time()
        self._prune_old_entries(now)

        if self._in_cooldown(now):
            return False
        if self._session_count() >= self._config.max_per_session:
            return False
        if self._day_count(now) >= self._config.max_per_day:
            return False
        return True

    def record(self, success: bool) -> None:
        """Record a modification attempt."""
        entry = {"timestamp": time.time(), "success": success}
        self._state.setdefault("entries", []).append(entry)
        if not success:
            self._state["last_failure"] = time.time()
        self._save_state()

    def _in_cooldown(self, now: float) -> bool:
        last_fail = self._state.get("last_failure", 0)
        return (now - last_fail) < self._config.cooldown_after_failure_seconds

    def _session_count(self) -> int:
        session_start = self._state.get("session_start", time.time())
        return sum(
            1 for e in self._state.get("entries", [])
            if e["timestamp"] >= session_start
        )

    def _day_count(self, now: float) -> int:
        day_start = now - 86400
        return sum(
            1 for e in self._state.get("entries", [])
            if e["timestamp"] >= day_start
        )

    def _prune_old_entries(self, now: float) -> None:
        cutoff = now - 86400 * 7  # Keep 7 days of history
        self._state["entries"] = [
            e for e in self._state.get("entries", [])
            if e["timestamp"] > cutoff
        ]

    def _load_state(self) -> dict:
        if self._state_path.exists():
            return json.loads(self._state_path.read_text())
        return {"entries": [], "session_start": time.time()}

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._state, indent=2))

    def reset_session(self) -> None:
        """Mark a new session boundary."""
        self._state["session_start"] = time.time()
        self._save_state()


class ScopeGuard:
    """Immutable path protection. Blocks writes to protected paths."""

    def __init__(self, protected_paths: list[str]):
        self._protected = [Path(p).resolve() for p in protected_paths]

    def is_protected(self, path: str | Path) -> bool:
        """Check if a path is protected from modification."""
        target = Path(path).resolve()
        return any(
            target == p or p in target.parents
            for p in self._protected
        )

    def check_write(self, path: str | Path) -> None:
        """Raise if path is protected."""
        if self.is_protected(path):
            raise PermissionError(
                f"Write blocked: {path} is protected by scope guard"
            )


@dataclass
class RollbackEntry:
    modification_id: str
    path: str
    before: str
    after: str
    timestamp: float = field(default_factory=time.time)


class RollbackRegistry:
    """Every modification is reversible. No modification without a rollback record."""

    def __init__(self, registry_path: Path):
        self._path = registry_path
        self._entries: list[dict] = self._load()

    def record(self, modification_id: str, path: str, before: str, after: str) -> None:
        """Record a modification for potential rollback."""
        self._entries.append({
            "id": modification_id,
            "path": path,
            "before": before,
            "after": after,
            "timestamp": time.time(),
        })
        self._save()

    def rollback(self, modification_id: str) -> Optional[str]:
        """Rollback a specific modification. Returns the restored content."""
        entry = next((e for e in self._entries if e["id"] == modification_id), None)
        if entry is None:
            return None
        Path(entry["path"]).write_text(entry["before"])
        entry["rolled_back"] = True
        self._save()
        return entry["before"]

    def rollback_all_since(self, timestamp: float) -> int:
        """Rollback all modifications since a timestamp. Returns count."""
        count = 0
        for entry in reversed(self._entries):
            if entry["timestamp"] >= timestamp and not entry.get("rolled_back"):
                Path(entry["path"]).write_text(entry["before"])
                entry["rolled_back"] = True
                count += 1
        self._save()
        return count

    def _load(self) -> list[dict]:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._entries, indent=2))
