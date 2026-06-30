"""
Workfront Mock Integration.

Simulates the behavior of a Workfront MCP server (unavailable in this
environment) for retrieving briefings with a "Ready" status. It returns a
JSON payload that is 1:1 compatible with `BriefingJson` / `BriefingInput`,
allowing it to be passed directly as input to `/campaign/brief_insights_extraction`
or `/campaign/generate_copy_and_background`.

When the actual Workfront MCP server becomes available in the future,
`_fetch_ready_briefings_mock()` can simply be replaced with the real call
(e.g., via `httpx` to the Workfront MCP endpoint) while keeping the public
signature `get_ready_briefings(...)` unchanged.

NOTE: This module is purely a mock for development/demo purposes. It
does not make any actual network calls to Workfront.
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
        "raw_extraction": "[mock] Excerpt from Workfront — 'Winter Ritual' briefing for FullCosmetics — The Force of Beauty. "
                          "Objective: launch of a 50ml regenerating night cream for the winter season...",
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
        "raw_extraction": "[mock] Excerpt from Workfront — 'Bright Start' briefing for FullCosmetics — The Force of Beauty. "
                          "Spring launch of Vitamin C serum, focusing on radiance and freshness...",
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
        "raw_extraction": "[mock] Excerpt from Workfront — 'Daily Comfort' briefing for FullCosmetics — The Force of Beauty. "
                          "Repositioning campaign for a daily-use moisturizing hand cream...",
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
        "raw_extraction": "[mock] Excerpt from Workfront — 'Shield Up' briefing for FullCosmetics — The Force of Beauty. "
                          "Launch of a daily sun fluid for the summer season, targeting active outdoor enthusiasts...",
    },
]


def _make_workfront_envelope(briefing: dict, index: int) -> dict:
    """
    It wraps the BriefingJson payload with metadata typical of a Workfront task,
    making the mock indistinguishable from a real Workfront MCP response.
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
    Simulates the latency and behavior of a real MCP call to Workfront.
    In the future, this function should be replaced with the actual call to the
    Workfront MCP server (e.g., using httpx.AsyncClient to the MCP endpoint
    exposed by Workfront, with OAuth/API key authentication).
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
    Public entry point — equivalent to the `get_ready_briefings` MCP tool
    expected from a real Workfront MCP server.

    Args:
        limit: maximum number of briefings to return (default 5).
        project_id: optional, filter by Workfront project (ignored in the mock).

    Returns:
        A dict containing the list of "Ready" briefings and their associated Workfront metadata.
        Each item contains a `briefing_payload` that can be used directly
        as the body for /api/v1/campaign/generate_copy_and_background or
        as a reference for comparison with /api/v1/campaign/brief_insights_extraction.
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