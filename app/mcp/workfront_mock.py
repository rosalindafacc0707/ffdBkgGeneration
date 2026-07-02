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
        "product": "CeraRepair Intensive Cream 50ml — Comfort Jar",
        "product_url": "https://contentgeneration2.blob.core.windows.net/productimages/12345-67890.png",
        "season": "Autumn/Winter 2026",
        "audience": "Men and women 20-45, compromised skin barrier, sensitive skin sufferers, colder climate residents. Searches for 'ceramides', 'skin barrier repair'.",
        "goal": "Launch the new rich soothing cream in the eco-friendly glass jar. Position as the ultimate winter savior for dry/irritated skin. Drive 40K units sold in Q4.",
        "tone_of_voice": "Dermatological, soothing, reassuring, clinical yet premium. Focused on efficacy and comfort.",
        "brand": "FullCosmetics — The Force of the Beauty",
        "campaign_name": "CeraRepair — The Barrier Shield",
        "key_messages": [
            "5 Essential Ceramides + Centella Asiatica for immediate barrier repair.",
            "Ultra-rich cream texture, zero greasy residue.",
            "72-hour locked-in hydration clinically proven.",
            "Fragrance-free, hypoallergenic, non-comedogenic.",
        ],
        "raw_extraction": "[mock] Workfront-ready brief derived from FC_Brief_WF2026006_CeraRepair_Cream-v2.xlsx.",
    },
    {
        "product": "Retinol Lift 0.5% Night Cream 30ml — Aluminum Precision Tube",
        "product_url": "https://contentgeneration2.blob.core.windows.net/productimages/67890-12345.png",
        "season": "Winter 2026 / Pre-launch",
        "audience": "Aged 30-55, looking for powerful anti-aging solutions, high awareness of active ingredients (retinol, peptides). Expects high performance.",
        "goal": "Introduce the stabilized 0.5% pure retinol cream in an airtight aluminum tube to preserve potency. Generate 5,000 subscription renewals within 60 days.",
        "tone_of_voice": "Bold, scientific, authoritative, result-oriented. Highlighting technological breakthrough in stability.",
        "brand": "FullCosmetics — The Force of the Beauty",
        "campaign_name": "Retinol Lift — Age Eraser",
        "key_messages": [
            "0.5% Pure Stabilized Retinol + Copper Peptides.",
            "Airtight aluminum tube prevents oxidation — full potency until the last drop.",
            "-37% wrinkle depth in 6 weeks, validated by independent clinical trials.",
            "Formulated to minimize purging and redness.",
        ],
        "raw_extraction": "[mock] Workfront-ready brief derived from FC_Brief_WF2026007_RetinolLift_Tube-v2.xlsx.",
    },
    {
        "product": "Glow Radiance Vitamin C Cream 50ml — Amber Glass Jar",
        "product_url": "https://contentgeneration2.blob.core.windows.net/productimages/12345-67890.png",
        "season": "Late Summer / Early Autumn 2026",
        "audience": "Gen-Z and Millennials (18-35), dull skin concerns, city lifestyle, social media active, looking for immediate glow and pollution defense.",
        "goal": "Launch the new Vitamin C morning cream in an amber protective jar. Position as the ultimate morning wake-up juice for tired skin. Achieve viral TikTok visibility.",
        "tone_of_voice": "Energetic, fresh, vibrant, uplifting. Friendly skin-positivity.",
        "brand": "FullCosmetics — The Force of the Beauty",
        "campaign_name": "Glow Radiance — Vitamin C Booster",
        "key_messages": [
            "10% Vitamin C + Ferulic Acid for multi-level brightening.",
            "Sorbet-cream texture that instantly revives dull skin.",
            "Anti-pollution shield ideal for urban environments.",
            "Citrus-fresh natural scent.",
        ],
        "raw_extraction": "[mock] Workfront-ready brief derived from FC_Brief_WF2026008_GlowRadiance_Cream-v2.xlsx.",
    },
    {
        "product": "HydroSoothe Calming Melt-In Cream 50ml — Luxury Glass Jar",
        "product_url": "https://contentgeneration2.blob.core.windows.net/productimages/12345-67890.png",
        "season": "Spring/Summer 2027",
        "audience": "Aged 20-35, combination to dry dehydrated skin, looking for intense hydration without heavy sensory feel. Heavy users of social routine videos.",
        "goal": "Launch the new light melt-in cream in the frosted glass jar. Highlight the transition from a rich cream to a fresh water-burst feel upon application. Drive 35K units in first season.",
        "tone_of_voice": "Fresh, lightweight, sensory, poetic yet clinical. Focus on texture transformation.",
        "brand": "FullCosmetics — The Force of the Beauty",
        "campaign_name": "HydroSoothe — Deep Oasis",
        "key_messages": [
            "Blue Algae extract + Squalane for instant plumping.",
            "Unique melt-in sensory texture: rich cream turns to fresh moisture on contact.",
            "+110% immediate moisture boost verified by skin-hydration mapping.",
            "Clean formula, glass jar infinitely recyclable.",
        ],
        "raw_extraction": "[mock] Workfront-ready brief derived from FC_Brief_WF2026009_HydroSoothe_Cream.xlsx.",
    },
    {
        "product": "Peptide Sculpt Resurfacing Cream 40ml — Targeted Metal-Tip Tube",
        "product_url": "https://contentgeneration2.blob.core.windows.net/productimages/67890-12345.png",
        "season": "Winter 2026 / Q4 High Performance",
        "audience": "Aged 35-60, concerned with skin sagging, loss of elasticity around jawline and neck, 'tech-neck' line lines. High-intent skin solutions buyers.",
        "goal": "Introduce the intensive peptide firming cream in its special direct-application metal-tip tube. Drive immediate conversion through high-performance routine video demonstrations.",
        "tone_of_voice": "Lifting, architectural, sophisticated, precise. Clinical definition meets high-end sculpture.",
        "brand": "FullCosmetics — The Force of the Beauty",
        "campaign_name": "Peptide Sculpt — Neck & Jaw Definer",
        "key_messages": [
            "Triple-Peptide Matrix + Vegan Collagen for precise restructuring.",
            "Precision ergonomic metal applicator cools, depuffs and sculpts during application.",
            "Visibly firmer jawline and smooth neck folds in 4 weeks.",
            "Fast-absorbing targeted formula designed for lifting massage.",
        ],
        "raw_extraction": "[mock] Workfront-ready brief derived from FC_Brief_WF2026010_PeptideSculpt_Tube.xlsx.",
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