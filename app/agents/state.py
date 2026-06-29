"""
CampaignState — shared state of the LangGraph graph.

For parallel execution (fan-out), LangGraph requires that fields
which can be written by multiple nodes use `Annotated` with a
merge function. Without it, it raises INVALID_CONCURRENT_GRAPH_UPDATE.

Strategy:
- briefing:  immutable, never overwritten by nodes → no merge needed,
             but we use `keep_first` for safety
- copy:      written only by copywriter → `keep_last` (overwrites None)
- visual:    written only by visual_expert → `keep_last` (overwrites None)
- errors:    written by both → `merge_lists` (accumulates all errors)
"""
from typing import Optional, Annotated
from typing_extensions import TypedDict
from app.core.schemas import BriefingInput, CopyResult, VisualResult


# ── Merge Functions ────────────────────────────────────────────────────────

def keep_first(a, b):
    """Keep the first non-None value. Used for immutable fields."""
    return a if a is not None else b


def keep_last(a, b):
    """Keep the last non-None value. Used for fields written by a single node."""
    return b if b is not None else a


def merge_lists(a: list, b: list) -> list:
    """Merges two lists. Used for errors (written by both nodes)."""
    return (a or []) + (b or [])


# ── State ────────────────────────────────────────────────────────────────

class CampaignState(TypedDict):
    briefing: Annotated[Optional[BriefingInput], keep_first]
    copy:     Annotated[Optional[CopyResult],    keep_last]
    visual:   Annotated[Optional[VisualResult],  keep_last]
    errors:   Annotated[list[str],               merge_lists]
