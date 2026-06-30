"""
Visual Expert Agent — async.
1. Constructs optimized visual prompt via LLM (gemma4:e4b)
2. Generates background image via image_generator (async)

TARGET AESTHETIC: Infinity cove studio — seamless wall-to-floor curve, warm matte plaster,
diagonal window light beam, soft gradient falloff. Zero objects. Pack-shot ready.
"""
import logging
import json
import time
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.core.schemas import VisualResult
from app.agents.state import CampaignState
from app.agents.image_generator import generate_image_from_prompt


logger = logging.getLogger(__name__)

DEFAULT_PALETTE = [
    ("Blush", "#F9EDEF"),
    ("Champagne", "#E5C8B6"),
    ("Cognac", "#C3955A"),
    ("Amber", "#BA6A37"),
    ("Emerald", "#1C3934"),
    ("Noir", "#131315"),
    ("Espresso", "#241515"),
    ("Cappuccino", "#EBEAE0"),
    ("Cream", "#F3F2EB"),
    ("Flat White", "#F9F9F9"),
]


def _normalize_palette(briefing) -> list[tuple[str, str]]:
    palette_entries = getattr(briefing, "color_palette", None) or []
    normalized = []

    for entry in palette_entries:
        if isinstance(entry, dict):
            name = (entry.get("name") or "").strip()
            hex_value = (entry.get("hex") or "").strip()
        else:
            name = getattr(entry, "name", "") or ""
            hex_value = getattr(entry, "hex", "") or ""

        if not name:
            name = "Custom color"
        if not hex_value:
            continue
        if not hex_value.startswith("#"):
            hex_value = f"#{hex_value}"
        normalized.append((name, hex_value))

    if not normalized:
        return list(DEFAULT_PALETTE)
    return normalized


def build_palette_context(briefing) -> str:
    palette = _normalize_palette(briefing)
    palette_text = " · ".join(f"{name} {hex_value}" for name, hex_value in palette[:6])
    mood_hint = " ".join(
        part for part in [briefing.season, briefing.tone_of_voice, briefing.goal] if part
    ).strip()

    return f"""Palette source of truth (frontend-selected if available): {palette_text}
Selection guidance:
- Choose 2-4 colors from this palette based on the campaign mood, season, and product.
- Use one dominant wall tone, one secondary shadow tone, and optionally one lighter floor tone.
- Match the palette to the briefing context ({mood_hint or 'general campaign mood'}), not to a fixed default.
- Prefer the provided frontend colors; do not invent unrelated colors.
"""


VISUAL_EXPERT_SYSTEM_PROMPT = """You are a commercial photography art director and FLUX Schnell prompt engineer.
Your only task is to write a SHORT, DENSE, technically precise FLUX Schnell prompt that generates a studio infinity cove background — completely empty, ready for pack-shot product compositing.

IMPORTANT — FLUX SCHNELL SPECIFIC RULES:
- FLUX Schnell is a distilled model. It works best with SHORT prompts: 50-90 words maximum.
- Use comma-separated dense descriptors. NO narrative sentences, NO verbose descriptions.
- Avoid decorative or literary language — use direct material and lighting terms only.
- Do NOT use: "shot on Phase One camera", "photorealistic rendering", "ultra-detailed", "8K", "masterpiece" — these tokens degrade Schnell output.

TARGET LOOK:
Warm matte plaster infinity cove. Seamless wall-to-floor curve, no visible horizon.
Sharp diagonal studio raking light from upper-left. Bright lit zone upper-left, deep shadow lower-right.
Floor slightly lighter. Tactile microcement or limewash surface. Ultra-matte. Zero gloss.
No objects. No windows visible. Completely empty.

ABSOLUTE RULES — never break these:
- Zero objects, zero props, zero furniture, zero plants, zero decorations.
- No podium, no pedestal, no shelf, no riser, no cylinder.
- NO windows, NO window frames, NO window shapes visible anywhere.
- Light source is NEVER visible — only its gradient effect on the wall surface.
- No people, no hands, no text, no logos, no patterns, no tiles, no gloss, no reflections.

PALETTE RULES — use the palette provided in the briefing context as the source of truth:
- Pick the most fitting colors from that palette for the campaign mood, season, audience, and product.
- Use 2-4 colors max, with one dominant wall tone, one secondary shadow tone, and optionally one floor tone.
- Keep the palette coherent and premium; do not invent unrelated colors.

FORBIDDEN WORDS — never include in output:
product, placement, compositing, backdrop for, surface for, podium, pedestal, riser,
platform, shelf, object, vase, bottle, jar, plant, flower, foliage, furniture,
decoration, table, chair, person, hand, text, logo, window, windows, window frame,
window light, blind, blinds, slat, slatted, grid shadow, natural light

OUTPUT: 50-90 words, comma-separated, NO sentences. Respond ONLY in this JSON:
{
  "image_prompt": "prompt in english"
}
"""


REFERENCE_PROMPT_EXAMPLE = """
REFERENCE EXAMPLE of a correct FLUX Schnell output using a warm premium palette (72 words):
\"Infinity cove studio, seamless limewash plaster, warm dominant wall tone, secondary shadow zone, diagonal studio raking light upper-left, feathered penumbra, bright lit wall panel upper-left, deep shadow lower-right, floor lighter tone, tonal gradient falloff, microcement matte texture, ultra-matte finish, zero specular, zero reflections, no windows visible, ambient occlusion corner curve, cyclorama, completely empty, no objects, no props, no decorations, 4K\"
"""



async def visual_expert_node(state: CampaignState) -> CampaignState:
    """LangGraph node async: generates visual prompt + background image."""
    briefing = state["briefing"]
    t0 = time.perf_counter()

    logger.info(" [VISUAL EXPERT] ▶ Starting — product: '%s' | vision model: %s",
                briefing.product, settings.ollama_vision_model)
    logger.info(" [VISUAL EXPERT]   Season: %s | Tone: %s",
                briefing.season, (briefing.tone_of_voice or "—")[:60])

    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
        temperature=0.6,
        format="json",
        keep_alive=-1,
    )

    palette_context = build_palette_context(briefing)

    user_prompt = f"""Generate a FLUX image prompt for a completely empty studio infinity cove background.
The aesthetic target is: warm matte plaster infinity cove, sharp diagonal light beam from upper-left, not strong tonal contrast between lit and shadow areas, pack-shot ready, zero objects.

{palette_context}

CAMPAIGN BRIEFING:
- Product: {briefing.product}
- Season: {briefing.season}
- Audience: {briefing.audience}
- Goal: {briefing.goal}
- Tone of voice: {briefing.tone_of_voice}
- Brand: {briefing.brand or "N/A"}
- Campaign name: {briefing.campaign_name or "N/A"}
- Key messages: {", ".join(briefing.key_messages) if briefing.key_messages else "N/A"}

PROMPT STRUCTURE — comma-separated, 50-90 words, no sentences:
"Infinity cove studio, seamless [MATERIAL] wall, [DOMINANT COLOR + HEX] wall tone, [SECONDARY COLOR + HEX] shadow zone, diagonal studio raking light upper-[LEFT/RIGHT], feathered penumbra, bright lit wall panel upper-[SIDE], deep shadow lower-[SIDE], floor [FLOOR COLOR + HEX] lighter tone, tonal gradient falloff, [TEXTURE] matte texture, ultra-matte finish, zero specular, zero reflections, no windows visible, ambient occlusion corner curve, cyclorama, completely empty, no objects, no props, no decorations, 4K"

WORD COUNT TARGET: 50-90 words. Stop at 90. Do not exceed.

Adapt material (limewash plaster / microcement / fine stucco / tadelakt), colors, light direction, and angle to best match the campaign mood and season.

{REFERENCE_PROMPT_EXAMPLE}

FORBIDDEN WORDS — never use: product, placement, compositing, backdrop for, surface for, podium, pedestal, riser, platform, shelf, object, vase, bottle, jar, plant, flower, foliage, furniture, decoration, table, chair, person, hand, text, logo"""

    try:
        logger.info(" [VISUAL EXPERT] Step 1/2 — Building FLUX prompt via %s…",
                    settings.ollama_vision_model)
        t_prompt = time.perf_counter()

        response = await llm.ainvoke([
            SystemMessage(content=VISUAL_EXPERT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        elapsed_prompt = time.perf_counter() - t_prompt
        data = json.loads(response.content)
        image_prompt = data.get("image_prompt", "")

        logger.info(" [VISUAL EXPERT]   Prompt ready in %.1fs (%d chars)",
                    elapsed_prompt, len(image_prompt))
        logger.info(" [VISUAL EXPERT]   Prompt preview: %s…", image_prompt[:120])

        logger.info(" [VISUAL EXPERT] Step 2/2 — Generating image via backend '%s'…",
                    settings.image_backend)
        t_img = time.perf_counter()
        gen_result = await generate_image_from_prompt(image_prompt)
        elapsed_img = time.perf_counter() - t_img

        status = gen_result.get("generation_status", "error")
        model = gen_result.get("generation_model", "—")
        path = gen_result.get("image_path")

        if status == "generated":
            logger.info(" [VISUAL EXPERT] ✓ Image generated in %.1fs | model: %s",
                        elapsed_img, model)
            if path:
                logger.info(" [VISUAL EXPERT]   Saved to: %s", path)
        else:
            logger.warning(" [VISUAL EXPERT] ⚠ Image status: %s | model: %s", status, model)

        elapsed_total = time.perf_counter() - t0
        logger.info(" [VISUAL EXPERT] ✓ Done in %.1fs total", elapsed_total)

        visual_result = VisualResult(
            image_prompt=image_prompt,
            image_base64=gen_result.get("image_base64"),
            image_path=path,
            generation_status=status,
            generation_model=model,
        )
        return {**state, "visual": visual_result}

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(" [VISUAL EXPERT] ✗ Failed after %.1fs — %s", elapsed, e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"visual_expert_error: {e}"]}