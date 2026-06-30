"""
Workfront Mock Integration.

Simula il comportamento di un MCP server Workfront (non disponibile in questo
ambiente) per il recupero di briefing in stato "Ready". Restituisce un payload
JSON compatibile 1:1 con `BriefingJson` / `BriefingInput`, così può essere
passato direttamente come input a `/campaign/brief_insights_extraction`
oppure a `/campaign/generate_copy_and_background`.

Quando in futuro sarà disponibile il vero MCP server Workfront, basterà
sostituire `_fetch_ready_briefings_mock()` con la chiamata reale (es. via
httpx verso l'endpoint MCP di Workfront) mantenendo invariata la firma
pubblica `get_ready_briefings(...)`.

NOTE: questo modulo è puramente un mock a scopo di sviluppo/demo. Non
effettua alcuna chiamata di rete reale verso Workfront.
"""
import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

SEPARATOR = "─" * 60

# ── Dataset mock — briefing realistici in stato "Ready" ────────────────────
# Ogni elemento è già nel formato BriefingJson (compatibile con
# /campaign/brief_insights_extraction e /campaign/generate_copy_and_background)

_MOCK_BRIEFINGS_POOL = [
    {
        "product": "Regenerating Night Cream 50ml",
        "season": "Winter 2025",
        "audience": "Women 35-55, skin-conscious, premium lifestyle",
        "goal": "Increase brand awareness in the premium skincare segment",
        "tone_of_voice": "Sophisticated, reassuring, slightly clinical",
        "brand": "FullCosmetics",
        "campaign_name": "Winter Ritual",
        "key_messages": [
            "Deep regeneration overnight",
            "Clinically tested formula",
            "Luxury skincare ritual",
        ],
        "raw_extraction": "[mock] Estratto da Workfront — Briefing 'Winter Ritual' per FullCosmetics — The Force of Beauty. "
                          "Obiettivo: lancio crema rigenerante notte 50ml per la stagione invernale...",
    },
    {
        "product": "Vitamin C Brightening Serum 30ml",
        "season": "Spring 2026",
        "audience": "Women 25-40, urban professionals, skincare enthusiasts",
        "goal": "Drive trial and online sales for the new serum launch",
        "tone_of_voice": "Energetic, fresh, science-backed",
        "brand": "FullCosmetics",
        "campaign_name": "Bright Start",
        "key_messages": [
            "10% pure Vitamin C complex",
            "Visible radiance in 7 days",
            "Dermatologist approved",
        ],
        "raw_extraction": "[mock] Estratto da Workfront — Briefing 'Bright Start' per FullCosmetics — The Force of Beauty. "
                          "Lancio siero vitamina C per primavera, focus su luminosità e freschezza...",
    },
    {
        "product": "Hydrating Hand Cream 75ml",
        "season": "Q1 2026",
        "audience": "Adults 30-60, dry skin concerns, practical daily users",
        "goal": "Reposition as the everyday hydration essential",
        "tone_of_voice": "Warm, practical, comforting",
        "brand": "FullCosmetics",
        "campaign_name": "Daily Comfort",
        "key_messages": [
            "24h moisture lock",
            "Non-greasy fast absorption",
            "Suitable for sensitive skin",
        ],
        "raw_extraction": "[mock] Estratto da Workfront — Briefing 'Daily Comfort' per FullCosmetics — The Force of Beauty. "
                          "Campagna di riposizionamento per crema mani idratante uso quotidiano...",
    },
    {
        "product": "SPF50 Daily Defense Fluid 40ml",
        "season": "Summer 2026",
        "audience": "Adults 20-45, sun-conscious, active outdoor lifestyle",
        "goal": "Build category leadership in daily sun protection",
        "tone_of_voice": "Confident, protective, modern",
        "brand": "FullCosmetics",
        "campaign_name": "Shield Up",
        "key_messages": [
            "Broad spectrum SPF50 protection",
            "Weightless invisible finish",
            "Reef-safe formula",
        ],
        "raw_extraction": "[mock] Estratto da Workfront — Briefing 'Shield Up' per FullCosmetics — The Force of Beauty. "
                          "Lancio fluido solare quotidiano per la stagione estiva, target attivo outdoor...",
    },
]


def _make_workfront_envelope(briefing: dict, index: int) -> dict:
    """
    Avvolge il payload BriefingJson con metadati tipici di un task Workfront,
    cosi' il mock e' indistinguibile da una vera risposta MCP Workfront.
    """
    now = datetime.now(timezone.utc)
    task_id = f"WF-{uuid.uuid4().hex[:8].upper()}"
    entry_date = now - timedelta(days=random.randint(1, 10))

    return {
        "workfront_task_id": task_id,
        "workfront_project_id": f"PRJ-{1000 + index}",
        "status": "Ready",
        "entry_date": entry_date.isoformat(),
        "last_updated": now.isoformat(),
        "assigned_to": "marketing.team@fullcosmetics.example",
        # Payload pronto per /api/v1/campaign/brief_insights_extraction
        # (ha la stessa shape dell'output del vero endpoint, cosi' puo'
        # essere usato direttamente anche come input di generate_copy_and_background)
        "briefing_payload": briefing,
    }


async def _fetch_ready_briefings_mock(
    limit: int = 5,
    project_id: Optional[str] = None,
) -> list[dict]:
    """
    Simula la latenza e il comportamento di una vera chiamata MCP a Workfront.
    In futuro questa funzione va sostituita con la chiamata reale al
    Workfront MCP server (es. tramite httpx.AsyncClient verso l'endpoint
    MCP esposto da Workfront, con autenticazione OAuth/API key).
    """
    logger.info("   [WORKFRONT MOCK] Simulating network round-trip…")
    import asyncio
    await asyncio.sleep(0.3)  # simula latenza di rete realistica

    pool = _MOCK_BRIEFINGS_POOL
    if project_id:
        # in un'integrazione reale questo sarebbe un filtro server-side;
        # qui semplicemente non filtriamo nulla (mock) ma logghiamo l'intento
        logger.info("   [WORKFRONT MOCK] Filter requested for project_id='%s' (ignored in mock)",
                    project_id)

    selected = pool[: max(0, min(limit, len(pool)))]
    return [_make_workfront_envelope(b, i) for i, b in enumerate(selected)]


async def get_ready_briefings(
    limit: int = 5,
    project_id: Optional[str] = None,
) -> dict:
    """
    Entry point pubblico — equivalente del tool MCP `get_ready_briefings`
    che ci si aspetta da un vero Workfront MCP server.

    Args:
        limit: numero massimo di briefing da restituire (default 5).
        project_id: opzionale, filtro per progetto Workfront (ignorato nel mock).

    Returns:
        dict con la lista di briefing "Ready" e i relativi metadati Workfront.
        Ogni elemento contiene `briefing_payload`, utilizzabile direttamente
        come body per /api/v1/campaign/generate_copy_and_background oppure
        come riferimento di confronto per /api/v1/campaign/brief_insights_extraction.
    """
    t0 = time.perf_counter()
    logger.info(SEPARATOR)
    logger.info("▶  WORKFRONT MOCK — get_ready_briefings called")
    logger.info("   limit       : %d", limit)
    logger.info("   project_id  : %s", project_id or "—")

    briefings = await _fetch_ready_briefings_mock(limit=limit, project_id=project_id)

    elapsed = time.perf_counter() - t0
    logger.info("✓  WORKFRONT MOCK — Returned %d briefing(s) in %.2fs", len(briefings), elapsed)
    for b in briefings:
        logger.info("   • %s | %s | product: %s",
                    b["workfront_task_id"], b["status"], b["briefing_payload"]["product"])
    logger.info(SEPARATOR)

    return {
        "source": "workfront_mock",
        "status": "ok",
        "count": len(briefings),
        "briefings": briefings,
    }