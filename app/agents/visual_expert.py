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

# UPDATED: Implemented literal, physical descriptors for FLUX Schnell color fidelity
DEFAULT_PALETTE = [
    ("delicate pale shell pink / soft pastel blush white with a subtle rosy undertone", "#F9EDEF"),
    ("muted dusty rose-beige / sophisticated nude beige with a soft pinkish clay undertone", "#E5C8B6"),
    ("rich toffee gold / warm caramel ochre brown", "#C3955A"),
    ("burnt terracotta orange / deep rustic amber earth tone", "#BA6A37"),
    ("deep forest green / matte midnight emerald dark pine", "#1C3934"),
    ("absolute obsidian black / deep matte jet black", "#131315"),
    ("deep dark chocolate brown / near-black espresso tone", "#241515"),
    ("light warm greige / pale sandy minimalist gray", "#EBEAE0"),
    ("warm ivory cream / soft off-white with a gentle buttery undertone", "#F3F2EB"),
    ("pure crisp minimalist white / bright matte studio white", "#F9F9F9"),
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


def _hex_to_luminance(hex_value: str) -> float:
    """Perceived luminance (0=dark, 1=light) from a hex color string."""
    hex_clean = hex_value.lstrip("#").strip()
    if len(hex_clean) != 6:
        return 0.5  # unknown/invalid → neutral, don't let it skew sorting
    try:
        r = int(hex_clean[0:2], 16) / 255.0
        g = int(hex_clean[2:4], 16) / 255.0
        b = int(hex_clean[4:6], 16) / 255.0
    except ValueError:
        return 0.5
    return 0.299 * r + 0.587 * g + 0.114 * b


def _classify_season(season: str) -> str:
    """Buckets a free-text season into 'dark' (winter/autumn), 'light' (spring/summer), or 'neutral'."""
    season_lower = (season or "").lower()
    dark_keywords = ("winter", "autumn", "fall")
    light_keywords = ("spring", "summer")

    if any(keyword in season_lower for keyword in dark_keywords):
        return "dark"
    if any(keyword in season_lower for keyword in light_keywords):
        return "light"
    return "neutral"


def _order_palette_by_season(palette: list[tuple[str, str]], season: str) -> list[tuple[str, str]]:
    """
    Reorders the palette so the most season-appropriate tones come first:
    - winter/autumn → darkest colors first
    - spring/summer → lightest colors first
    - anything else → left in original order
    """
    season_bucket = _classify_season(season)
    if season_bucket == "dark":
        return sorted(palette, key=lambda entry: _hex_to_luminance(entry[1]))
    if season_bucket == "light":
        return sorted(palette, key=lambda entry: _hex_to_luminance(entry[1]), reverse=True)
    return list(palette)


def build_palette_context(briefing) -> str:
    raw_palette = _normalize_palette(briefing)
    season = briefing.season
    season_bucket = _classify_season(season)

    ordered_palette = _order_palette_by_season(raw_palette, season)
    palette_text = " · ".join(f"{name} {hex_value}" for name, hex_value in ordered_palette[:6])

    mood_hint = " ".join(
        part for part in [briefing.season, briefing.tone_of_voice, briefing.goal] if part
    ).strip()

    # UPDATED: Season-driven tonal preference — dark palette for winter/autumn, light palette for spring/summer
    if season_bucket == "dark":
        season_rule = (
            f"- SEASON RULE (Winter/Autumn detected — '{season}'): prioritize the DEEP/DARK end of the "
            "palette above (obsidian black, deep chocolate, forest green, burnt terracotta, deep shadow tones). "
            "The dominant wall tone and shadow tone should both skew dark. Lighter tones from the palette, if "
            "used at all, should appear only as a minor accent or floor highlight, never dominant."
        )
    elif season_bucket == "light":
        season_rule = (
            f"- SEASON RULE (Spring/Summer detected — '{season}'): prioritize the LIGHT/PALE end of the "
            "palette above (blush white, ivory cream, pale greige, crisp studio white). The dominant wall tone "
            "and floor tone should both skew light and airy. Darker tones from the palette, if used at all, "
            "should appear only as a subtle shadow accent, never dominant."
        )
    else:
        season_rule = (
            f"- SEASON RULE: season '{season}' has no explicit dark/light bias — choose freely from the "
            "palette based on mood and product fit."
        )

    return f"""Palette source of truth (frontend-selected if available, reordered for season fit): {palette_text}
Selection guidance:
- Choose 2-4 colors from this palette based on the campaign mood, season, and product.
- Use one dominant wall tone, one secondary shadow tone, and optionally one lighter floor tone.
- Match the palette to the briefing context ({mood_hint or 'general campaign mood'}), not to a fixed default.
- Use only the provided frontend colors; do not invent unrelated colors.
{season_rule}
- CRITICAL FOR FLUX: To avoid destroying the pink/beige tones, always enforce 'neutral white studio lighting' or 'clean white illumination' to prevent yellow color shifts.
"""


VISUAL_EXPERT_SYSTEM_PROMPT = """You are a commercial photography art director and FLUX Schnell prompt engineer.
Your task is to write a SHORT, DENSE, artistically tuned FLUX Schnell prompt that generates an abstract, painterly studio backdrop — evocative, minimal, completely empty, and pack-shot ready.

IMPORTANT — FLUX SCHNELL SPECIFIC RULES:
- FLUX Schnell is a distilled model. It works best with SHORT prompts: 50-90 words maximum.
- Use comma-separated dense descriptors. NO narrative sentences, NO verbose descriptions.
- Favor artistic/visual terms (painterly wash, tonal fields, soft vignette, micrograin) over photographic gear shout-outs.
- Do NOT use: "shot on Phase One camera", "photorealistic rendering", "ultra-detailed", "8K", "masterpiece" — these tokens degrade Schnell output.

TARGET LOOK (ARTISTIC):
Abstract tonal backdrop, painterly gradient wash, soft directional wash of light, no defined floor-wall seam or horizon, subtle texture (canvas, brushed plaster, paper), gentle micrograin, soft vignetting, minimal contrast, atmospheric penumbra.
Suggest mood via color fields, not by placing objects or surfaces.

ABSOLUTE RULES — never break these:
- Zero objects, zero props, zero furniture, zero plants, zero decorations.
- No podium, no pedestal, no shelf, no riser, no cylinder.
- NO windows, NO window frames, NO window shapes visible anywhere.
- Light source is NEVER visible — only its gradient effect across the tonal field.
- No people, no hands, no text, no logos, no patterns that read as repeat tiles, no gloss, no strong reflections.

PALETTE RULES — use the palette provided in the briefing context as the source of truth:
- Pick the most fitting colors from that palette for the campaign mood, season, audience, and product.
- Use 2-4 colors max, with one dominant tonal field, one supporting shadow/shift, and an optional accent.
- Keep the palette coherent and artistic; do not invent unrelated colors.
- Respect the SEASON RULE included in the briefing context: winter/autumn briefs must skew the dominant and shadow tones DARK; spring/summer briefs must skew the dominant and floor tones LIGHT.

FORBIDDEN WORDS — never include in output:
product, placement, compositing, backdrop for, surface for, podium, pedestal, riser,
platform, shelf, object, vase, bottle, jar, plant, flower, foliage, furniture,
decoration, table, chair, person, hand, text, logo, window, windows, window frame,
window light, blind, blinds, slat, slatted, grid shadow, natural light, yellow cast, warm glow

OUTPUT: 50-90 words, comma-separated, NO sentences. Respond ONLY in this JSON:
{
    "image_prompt": "prompt in english"
}
"""


# UPDATED: Reference example updated with the new FLUX-proof descriptive vocabulary
REFERENCE_PROMPT_EXAMPLE = """
REFERENCE EXAMPLE of an artistic FLUX Schnell output (approx. 68 words):
\"Abstract tonal backdrop, painterly muted dusty rose-beige #E5C8B6 wash, subtle deep dark chocolate brown #241515 shadow shift, neutral white studio lighting, feathered penumbra, soft vignette, canvas microtexture, brushed plaster grain, tonal gradient falloff, atmospheric haze, muted contrast, no horizon, no floor seam, zero yellow cast, completely empty studio, pack-shot ready\"
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

    # UPDATED: Enforced strict white light parameters inside the structural skeleton
    user_prompt = f"""Generate a FLUX image prompt for an artistic, abstract, completely empty studio backdrop.
The aesthetic target is: painterly tonal fields, soft gradient wash, subtle texture (canvas or brushed plaster), gentle directional light suggestion, low defined floor/horizon or hard floor seam, pack-shot ready, zero objects.

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
"Infinity cove studio, seamless [MATERIAL] wall, [DOMINANT COLOR + HEX] wall tone, [SECONDARY COLOR + HEX] deep shadow zone, diagonal neutral white studio raking light upper-[LEFT/RIGHT], feathered penumbra, bright lit wall panel upper-[SIDE], deep shadow lower-[SIDE], floor [FLOOR COLOR + HEX] lighter tone, tonal gradient falloff, zero yellow cast, [TEXTURE] matte texture, ultra-matte finish, zero specular, zero reflections, no windows visible, ambient occlusion corner curve, cyclorama, completely empty, no objects, no props, no decorations, 4K"

WORD COUNT TARGET: 50-90 words. Stop at 90. Do not exceed.

Adapt material (limewash plaster / microcement / fine stucco / tadelakt), colors, light direction, and angle to best match the campaign mood and season. Colors MUST follow the SEASON RULE above — do not default to light/pastel tones for a winter or autumn brief, and do not default to dark/deep tones for a spring or summer brief.

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