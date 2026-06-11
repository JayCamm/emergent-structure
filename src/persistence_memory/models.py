from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any


class MemoryState(str, Enum):
    ACTIVE = "active"
    VALIDATED = "validated"
    STALE = "stale"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"
    DELETED = "deleted"


class GateDecision(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNING = "allow_with_warning"
    QUARANTINE = "quarantine"
    IGNORE = "ignore"
    REFRESH_REQUIRED = "refresh_required"
    ABSTAIN = "abstain"


@dataclass
class MemoryItem:
    id: str
    text: str
    source: str = "unknown"
    context_scope: str = "global"
    created_at: float = field(default_factory=time)
    last_used_at: float | None = None
    valid_until: float | None = None
    state: MemoryState = MemoryState.ACTIVE

    relevance: float = 0.0
    confidence: float = 0.5
    importance: float = 0.5
    burden: float = 0.1
    risk: float = 0.1
    usefulness_score: float = 0.0
    harm_score: float = 0.0

    retrieval_count: int = 0
    help_count: int = 0
    harm_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.state in {MemoryState.ACTIVE, MemoryState.VALIDATED}


@dataclass
class TaskContext:
    query: str
    context_scope: str = "global"
    need: float = 0.5
    risk_tolerance: float = 0.5
    abstention_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredMemory:
    memory: MemoryItem
    score: float
    decision: GateDecision
    reasons: list[str] = field(default_factory=list)


@dataclass
class FeedbackEvent:
    memory_id: str
    outcome: str
    helped: bool = False
    harmed: bool = False
    contradicted: bool = False
    notes: str = ""
    weight: float = 1.0
