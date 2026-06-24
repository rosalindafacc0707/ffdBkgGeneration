"""
CampaignState — stato condiviso del grafo LangGraph.

Per l'esecuzione parallela (fan-out), LangGraph richiede che i campi
che possono essere scritti da più nodi usino `Annotated` con una
funzione di merge. Senza, lancia INVALID_CONCURRENT_GRAPH_UPDATE.

Strategia:
- briefing:  immutabile, non viene mai riscritto dai nodi → nessun merge necessario,
             ma usiamo `keep_first` per sicurezza
- copy:      scritto solo da copywriter → `keep_last` (sovrascrive None)
- visual:    scritto solo da visual_expert → `keep_last` (sovrascrive None)
- errors:    scritto da entrambi → `merge_lists` (accumula tutti gli errori)
"""
from typing import Optional, Annotated
from typing_extensions import TypedDict
from app.core.schemas import BriefingInput, CopyResult, VisualResult


# ── Funzioni di merge ────────────────────────────────────────────────────────

def keep_first(a, b):
    """Tieni il primo valore non-None. Usato per campi immutabili."""
    return a if a is not None else b


def keep_last(a, b):
    """Tieni l'ultimo valore non-None. Usato per campi scritti da un solo nodo."""
    return b if b is not None else a


def merge_lists(a: list, b: list) -> list:
    """Unisce due liste. Usato per errors (scritto da entrambi i nodi)."""
    return (a or []) + (b or [])


# ── State ────────────────────────────────────────────────────────────────────

class CampaignState(TypedDict):
    briefing: Annotated[Optional[BriefingInput], keep_first]
    copy:     Annotated[Optional[CopyResult],    keep_last]
    visual:   Annotated[Optional[VisualResult],  keep_last]
    errors:   Annotated[list[str],               merge_lists]
