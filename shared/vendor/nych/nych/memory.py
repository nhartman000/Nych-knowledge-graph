"""
NYCH Memory Update Module
=========================
State Persistence: Update symbolic state. Persist Knowledge. Version Control.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from nych.types import NychContext, NychPacket, NychState


@dataclass(frozen=True)
class MemoryUpdateResult:
    """Result of memory update."""
    state_persisted: bool
    knowledge_persisted: bool
    version_control_hash: str
    memory_id: str


class MemoryUpdate:
    """
    Memory Update - State Persistence.
    
    Update symbolic state. Persist Knowledge. Version Control.
    """
    
    def __init__(self) -> None:
        self._state_history: list[NychState] = []
        self._knowledge_base: dict[str, Any] = {}
        self._version_hashes: list[str] = []
    
    def update(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
        new_knowledge: dict[str, Any] | None = None,
    ) -> MemoryUpdateResult:
        """
        Update memory with new state and optionally new knowledge.
        
        Args:
            packet: The current NYCH packet.
            context: The current NYCH context.
            state: The current NYCH state.
            new_knowledge: Optional new knowledge to persist.
        
        Returns:
            MemoryUpdateResult with update status.
        """
        # Persist state
        self._state_history.append(state)
        state_persisted = True
        
        # Persist knowledge if provided
        knowledge_persisted = False
        if new_knowledge:
            domain = context.domain
            if domain not in self._knowledge_base:
                self._knowledge_base[domain] = {}
            self._knowledge_base[domain].update(new_knowledge)
            knowledge_persisted = True
        
        # Version control hash
        version_hash = self._compute_version_hash(packet, context, state)
        self._version_hashes.append(version_hash)
        
        memory_id = hashlib.sha256(
            f"{packet.packet_id}:{context.domain}:{len(self._state_history)}".encode()
        ).hexdigest()[:16]
        
        return MemoryUpdateResult(
            state_persisted=state_persisted,
            knowledge_persisted=knowledge_persisted,
            version_control_hash=version_hash,
            memory_id=memory_id,
        )
    
    def _compute_version_hash(
        self,
        packet: NychPacket,
        context: NychContext,
        state: NychState,
    ) -> str:
        """Compute version control hash for state snapshot."""
        snapshot = {
            "packet_id": packet.packet_id,
            "domain": context.domain,
            "state_current": state.current,
            "timestamp": len(self._state_history),
        }
        return hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def get_knowledge(self, domain: str) -> dict[str, Any]:
        """Retrieve knowledge for a domain."""
        return self._knowledge_base.get(domain, {})
    
    def get_state_history(self) -> list[NychState]:
        """Get the full state history."""
        return list(self._state_history)
