"""Intent-Based Coordination — DECLARE→REVIEW→EXECUTE protocol.

Enables multiple agents to operate in a shared environment without semantic
conflicts. Coordination emerges from the protocol, not from a central
decision-maker. Each agent declares intent before acting, the system reviews
for conflicts, and execution proceeds only when clear.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReviewResult(Enum):
    CLEAR = "clear"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    SUPERSEDED = "superseded"


class ConflictResolution(Enum):
    PRIORITY = "priority"
    FIRST_DECLARED = "first_declared"
    MERGE = "merge"
    ESCALATE = "escalate"
    RETRY_LATER = "retry_later"


class ActionStatus(Enum):
    DECLARED = "declared"
    REVIEWING = "reviewing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"
    BLOCKED = "blocked"


@dataclass
class Intent:
    agent_id: str
    action: str
    target: str
    rationale: str
    priority: int = 0  # Higher = more important
    ttl_seconds: float = 300.0  # 5 min default
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    status: ActionStatus = ActionStatus.DECLARED


@dataclass
class ConflictDetail:
    intent_id: str
    conflicting_intent_id: str
    conflict_type: str  # syntactic, semantic, transitive
    description: str


@dataclass
class ActionResult:
    intent_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None


class CoordinationProtocol:
    """DECLARE→REVIEW→EXECUTE coordination for multi-agent environments.

    No central orchestrator. Conflict detection is protocol-driven.
    Graceful degradation: if coordination is unavailable, agents operate
    uncoordinated with logged warnings.
    """

    def __init__(self, resolution_strategy: ConflictResolution = ConflictResolution.FIRST_DECLARED):
        self._intents: dict[str, Intent] = {}
        self._history: list[Intent] = []
        self._resolution_strategy = resolution_strategy

    # ─── DECLARE Phase ─────────────────────────────────────────

    def declare(self, intent: Intent) -> str:
        """Declare an intent before acting. Returns intent_id."""
        self._prune_expired()
        intent.status = ActionStatus.DECLARED
        self._intents[intent.id] = intent
        return intent.id

    def withdraw(self, intent_id: str) -> bool:
        """Withdraw a declared intent before execution."""
        intent = self._intents.get(intent_id)
        if intent and intent.status in (ActionStatus.DECLARED, ActionStatus.REVIEWING, ActionStatus.BLOCKED):
            intent.status = ActionStatus.WITHDRAWN
            self._archive(intent)
            return True
        return False

    # ─── REVIEW Phase ──────────────────────────────────────────

    def review(self, intent_id: str) -> tuple[ReviewResult, list[ConflictDetail]]:
        """Review a declared intent for conflicts. Returns result + details."""
        intent = self._intents.get(intent_id)
        if intent is None:
            return ReviewResult.CLEAR, []

        intent.status = ActionStatus.REVIEWING
        conflicts: list[ConflictDetail] = []

        for other_id, other in self._intents.items():
            if other_id == intent_id:
                continue
            if other.status in (ActionStatus.WITHDRAWN, ActionStatus.COMPLETED, ActionStatus.FAILED):
                continue

            # Syntactic conflict: same target
            if other.target == intent.target:
                if other.action == intent.action and other.agent_id != intent.agent_id:
                    conflicts.append(ConflictDetail(
                        intent_id=intent_id,
                        conflicting_intent_id=other_id,
                        conflict_type="duplicate",
                        description=f"Agent {other.agent_id} already declared same action on {intent.target}",
                    ))
                else:
                    conflicts.append(ConflictDetail(
                        intent_id=intent_id,
                        conflicting_intent_id=other_id,
                        conflict_type="syntactic",
                        description=f"Target conflict: {other.agent_id} is acting on {intent.target}",
                    ))

        if not conflicts:
            return ReviewResult.CLEAR, []

        # Check for duplicates vs conflicts
        if all(c.conflict_type == "duplicate" for c in conflicts):
            return ReviewResult.DUPLICATE, conflicts

        return ReviewResult.CONFLICT, conflicts

    def resolve(self, intent_id: str, conflicts: list[ConflictDetail]) -> bool:
        """Attempt to resolve conflicts. Returns True if intent can proceed."""
        intent = self._intents.get(intent_id)
        if intent is None:
            return False

        for conflict in conflicts:
            other = self._intents.get(conflict.conflicting_intent_id)
            if other is None:
                continue

            if self._resolution_strategy == ConflictResolution.PRIORITY:
                if intent.priority <= other.priority:
                    intent.status = ActionStatus.BLOCKED
                    return False

            elif self._resolution_strategy == ConflictResolution.FIRST_DECLARED:
                if intent.timestamp >= other.timestamp:
                    intent.status = ActionStatus.BLOCKED
                    return False

            elif self._resolution_strategy == ConflictResolution.ESCALATE:
                intent.status = ActionStatus.BLOCKED
                return False

            elif self._resolution_strategy == ConflictResolution.RETRY_LATER:
                intent.status = ActionStatus.BLOCKED
                return False

            elif self._resolution_strategy == ConflictResolution.MERGE:
                # Merge allows both to proceed
                pass

        return True

    # ─── EXECUTE Phase ─────────────────────────────────────────

    def begin_execution(self, intent_id: str) -> bool:
        """Mark intent as executing. Returns False if not in valid state."""
        intent = self._intents.get(intent_id)
        if intent and intent.status in (ActionStatus.DECLARED, ActionStatus.REVIEWING):
            intent.status = ActionStatus.EXECUTING
            return True
        return False

    def report_completion(self, intent_id: str, result: ActionResult) -> None:
        """Report that execution completed (success or failure)."""
        intent = self._intents.get(intent_id)
        if intent:
            intent.status = ActionStatus.COMPLETED if result.success else ActionStatus.FAILED
            self._archive(intent)

    # ─── Read Interface ────────────────────────────────────────

    def get_active_intents(self) -> list[Intent]:
        """All non-terminal intents."""
        self._prune_expired()
        return [
            i for i in self._intents.values()
            if i.status not in (ActionStatus.WITHDRAWN, ActionStatus.COMPLETED, ActionStatus.FAILED)
        ]

    def get_intents_for_target(self, target: str) -> list[Intent]:
        """All active intents targeting a specific resource."""
        return [i for i in self.get_active_intents() if i.target == target]

    def get_agent_intents(self, agent_id: str) -> list[Intent]:
        """All active intents from a specific agent."""
        return [i for i in self.get_active_intents() if i.agent_id == agent_id]

    def get_intent(self, intent_id: str) -> Optional[Intent]:
        return self._intents.get(intent_id)

    def get_history(self, limit: int = 50) -> list[Intent]:
        """Completed/failed/withdrawn intents."""
        return self._history[-limit:]

    # ─── Internal ──────────────────────────────────────────────

    def _prune_expired(self) -> None:
        """Remove intents that exceeded their TTL."""
        now = time.time()
        expired = [
            iid for iid, i in self._intents.items()
            if (now - i.timestamp) > i.ttl_seconds
            and i.status not in (ActionStatus.EXECUTING, ActionStatus.COMPLETED, ActionStatus.FAILED)
        ]
        for iid in expired:
            intent = self._intents[iid]
            intent.status = ActionStatus.WITHDRAWN
            self._archive(intent)

    def _archive(self, intent: Intent) -> None:
        """Move to history and remove from active."""
        self._history.append(intent)
        self._intents.pop(intent.id, None)
