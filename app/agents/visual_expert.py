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


VISUAL_EXPERT_SYSTEM_PROMPT = """You are a commercial photography art director and FLUX prompt engineer.
Your only task is to write a dense, technically precise FLUX prompt that generates a studio infinity cove background — completely empty, ready for pack-shot product compositing.

TARGET LOOK — study this reference carefully:
A warm matte plaster infinity cove. The wall and floor are seamlessly curved, no visible horizon line.
A sharp diagonal shaft of studio raking light enters from the upper-left, casting a bright angled beam across the wall surface.
The beam has soft feathered edges. No windows, no window frames, no window reflections are ever visible.
Surrounding areas fall into warm shadow creating strong tonal contrast.
The floor is slightly lighter and more diffused. The overall palette is warm and editorial — Amber, Cognac, or Champagne tones.
The surface feels tactile: limewash plaster or fine microcement. Matte. No gloss.
No objects. No furniture. No plants. No people. No text. Completely empty.
ABSOLUTE RULES:
- NO windows, NO window frames, NO window shapes, NO window reflections visible anywhere in the frame.
- Light source is NEVER visible — only its effect on the wall surface is shown.

TECHNICAL PROMPT REQUIREMENTS:
- Dense, comma-separated technical descriptors — NOT narrative sentences
- Use cinematography and photography vocabulary: "infinity cove", "limewash plaster", "raking light", "feathered penumbra", "tonal falloff", "cyclorama", "soft-box fill", "warm key light", "ambient occlusion corners"
- Specify color in hex or precise color names aligned with the brand palette
- Specify the light: direction, quality (hard/soft), beam angle, shadow behavior
- Specify the material: texture, finish (matte/satin), grain
- The diagonal window light beam IS ALLOWED and ENCOURAGED — it creates the signature editorial look
- Minimum 80 words, maximum 140 words

STRICT BRAND PALETTE — choose the most fitting for the campaign mood:
Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37
Emerald #1C3934 · Noir #131315 · Espresso #241515
Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

FORBIDDEN WORDS — never include in output:
product, placement, compositing, backdrop for, surface for, podium, pedestal, riser,
platform, shelf, object, vase, bottle, jar, plant, flower, foliage, furniture, decoration, table, chair, person, hand, text, logo,
window, windows, window frame, window light, window beam, blind, blinds, slat, slatted, grid shadow, natural light

OUTPUT FORMAT — respond ONLY in this JSON:
{
  "image_prompt": "prompt in english"
}
"""


REFERENCE_PROMPT_EXAMPLE = """
REFERENCE EXAMPLE of a correct output prompt (Amber/Cognac palette):
\"Infinity cove studio, seamless limewash plaster wall curving into matte floor, warm Amber #BA6A37 dominant tone, Cognac #C3955A shadow gradient, sharp diagonal studio raking light from upper-left, off-axis key light at 45-degree angle, feathered penumbra edges, no windows visible, bright illuminated wall panel upper-left, deep warm shadow lower-right, floor slightly lighter in Champagne #E5C8B6, tonal falloff from highlight to shadow, tactile microcement surface grain, ultra-matte finish, zero specular, no reflections, ambient occlusion in wall-floor corner curve, cyclorama backdrop, completely empty, no objects, no props, no decorations, studio photography, 4K, photorealistic, shot on Phase One camera\"
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

    user_prompt = f"""Generate a FLUX image prompt for a completely empty studio infinity cove background.
The aesthetic target is: warm matte plaster infinity cove, sharp diagonal light beam from upper-left, not strong tonal contrast between lit and shadow areas, pack-shot ready, zero objects.

Select the most fitting palette colors for this campaign's mood and season from:
Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37 · Emerald #1C3934 · Noir #131315 · Espresso #241515 · Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

CAMPAIGN BRIEFING:
- Product: {briefing.product}
- Season: {briefing.season}
- Audience: {briefing.audience}
- Goal: {briefing.goal}
- Tone of voice: {briefing.tone_of_voice}
- Brand: {briefing.brand or "N/A"}
- Campaign name: {briefing.campaign_name or "N/A"}
- Key messages: {", ".join(briefing.key_messages) if briefing.key_messages else "N/A"}

PROMPT STRUCTURE — follow this exact pattern, replacing values for the campaign:
"Infinity cove studio, seamless [MATERIAL] wall curving into matte floor, [DOMINANT COLOR + HEX] dominant tone, [SECONDARY COLOR + HEX] shadow gradient, sharp diagonal studio raking light from upper-[LEFT or RIGHT], off-axis key light at [ANGLE]-degree angle, feathered penumbra edges, no windows visible, bright illuminated wall panel upper-[SIDE], deep warm shadow lower-[SIDE], floor slightly lighter in [FLOOR COLOR + HEX], tonal falloff from highlight to shadow, tactile [TEXTURE] surface grain, ultra-matte finish, zero specular, no reflections, ambient occlusion in wall-floor corner curve, cyclorama backdrop, completely empty, no objects, no props, no decorations, studio photography, 4K, photorealistic, shot on Phase One camera"

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