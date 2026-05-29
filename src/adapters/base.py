"""Base adapter interface — the contract a gateway implements to integrate SHARD.

Any LLM agent gateway that wants to use SHARD's governance layer must implement
this interface. The adapter translates between the gateway's native memory/skill
representation and SHARD's governance protocols.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAdapter(ABC):
    """Abstract base for gateway adapters.

    A gateway adapter bridges between SHARD's governance layer and the
    gateway's native storage and execution mechanisms. Each method maps
    to a capability the gateway must provide.
    """

    # ─── Memory Bridge ─────────────────────────────────────────

    @abstractmethod
    def read_memory(self, memory_id: str) -> Optional[dict[str, Any]]:
        """Read a memory from the gateway's native storage."""
        ...

    @abstractmethod
    def write_memory(self, memory_id: str, content: dict[str, Any]) -> None:
        """Write a memory to the gateway's native storage."""
        ...

    @abstractmethod
    def list_memories(self, filter_fn: Optional[callable] = None) -> list[str]:
        """List memory IDs, optionally filtered."""
        ...

    @abstractmethod
    def delete_memory(self, memory_id: str) -> None:
        """Remove a memory from the gateway's native storage."""
        ...

    # ─── Skill Bridge ──────────────────────────────────────────

    @abstractmethod
    def list_skills(self) -> list[dict[str, Any]]:
        """List all skills registered in the gateway."""
        ...

    @abstractmethod
    def get_skill_metadata(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Get metadata for a specific skill."""
        ...

    @abstractmethod
    def invoke_skill(self, skill_id: str, context: dict[str, Any]) -> Any:
        """Invoke a skill through the gateway's execution mechanism."""
        ...

    @abstractmethod
    def register_skill(self, skill_id: str, metadata: dict[str, Any]) -> None:
        """Register a new skill in the gateway."""
        ...

    @abstractmethod
    def deregister_skill(self, skill_id: str) -> None:
        """Remove a skill from the gateway's registry."""
        ...

    # ─── Agent Bridge ──────────────────────────────────────────

    @abstractmethod
    def list_agents(self) -> list[str]:
        """List active agent IDs in the gateway."""
        ...

    @abstractmethod
    def send_to_agent(self, agent_id: str, message: dict[str, Any]) -> None:
        """Send a message to another agent through the gateway's routing."""
        ...

    # ─── Lifecycle ─────────────────────────────────────────────

    @abstractmethod
    def on_connect(self) -> None:
        """Called when SHARD connects to the gateway. Setup hook."""
        ...

    @abstractmethod
    def on_disconnect(self) -> None:
        """Called when SHARD disconnects. Cleanup hook."""
        ...
