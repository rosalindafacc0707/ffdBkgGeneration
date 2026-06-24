"""
Visual Expert Agent — async
1. Costruisce prompt visivo ottimizzato via LLM
2. Genera l'immagine background via image_generator (async)
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

VISUAL_EXPERT_SYSTEM_PROMPT = """You are an Art Director for dermatological and cosmetic advertising, expert in writing optimized prompts for the FLUX image generation model.

YOUR TASK: Write a prompt that generates a totally empty background — a flat matte wall with soft directional light and a barely perceptible floor gradient at the bottom. Nothing else exists in the frame.

WHAT THE IMAGE MUST BE:
A smooth flat matte painted wall lit by soft directional light (from left, right, top, or diagonal). The light creates gentle feathered shadow transitions across the wall surface. Near the bottom of the frame, a very soft tonal gradient suggests the floor — imperceptible, never a hard line.

ABSOLUTE RULES — never break these:
- Zero objects. Zero props. Zero geometry. Zero 3D shapes.
- No podium, no pedestal, no platform, no riser, no disc, no cylinder.
- No footrests, no lifts, no shelves, no tables, no stools, no chairs, no furniture.
- No products, no bottles, no jars, no plants, no flowers, no decorations.
- No people, no hands, no text, no logos, no patterns, no tiles, no architectural details.
- No reflections, no specular highlights, no gloss, no CGI look.
- Do NOT use these words in the output: "product", "placement", "compositing", "surface for", "backdrop for".

LIGHT: Soft directional light from left, right, top, or diagonal — freely chosen based on mood. Feathered shadows only, never sharp or geometric.

STRICT BRAND PALETTE — use ONLY these colors, no exceptions:
Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37
Emerald #1C3934 · Noir #131315 · Espresso #241515
Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

Choose ONE dominant wall color and optionally ONE secondary color for shadow depth.

PROMPT FORMAT:
- Start with: "Flat matte [color] wall, soft [direction] light..."
- Minimum 60 words, in English
- Describe: wall color, light direction, shadow behavior, atmosphere
- Always end with: "completely empty, no objects, no geometry, flat matte wall, matte finish, no reflections, barely perceptible tonal floor gradient at the bottom"

Respond ONLY in this JSON format:
{
  "image_prompt": "prompt in english"
}
"""

async def visual_expert_node(state: CampaignState) -> CampaignState:
    """LangGraph node async: generates visual prompt + background image."""
    briefing = state["briefing"]
    t0 = time.perf_counter()

    logger.info("  [VISUAL EXPERT] ▶ Starting — product: '%s' | vision model: %s",
                briefing.product, settings.ollama_vision_model)
    logger.info("  [VISUAL EXPERT]   Season  : %s | Goal: %s",
                briefing.season, briefing.goal[:60] if briefing.goal else "—")

    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
        temperature=0.7,
        format="json",
        keep_alive=-1,
    )

    user_prompt = f"""Generate a FLUX image prompt for an empty background wall that fits this campaign briefing.

FORBIDDEN WORDS in the output prompt: "product", "placement", "compositing", "backdrop for", "surface for", "podium", "pedestal", "riser", "platform", "shelf", "footrest", "lift", "object", "plant", "flower", "table", "chair".

Choose the most evocative wall color and light direction for this product and season.
Use ONLY brand palette colors: Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37 · Emerald #1C3934 · Noir #131315 · Espresso #241515 · Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

Campaign briefing:
- Product: {briefing.product}
- Season: {briefing.season}
- Audience: {briefing.audience}
- Goal: {briefing.goal}
- Tone of voice: {briefing.tone_of_voice}
- Brand: {briefing.brand or "N/A"}
- Campaign name: {briefing.campaign_name or "N/A"}
- Key messages: {", ".join(briefing.key_messages) if briefing.key_messages else "N/A"}

The output prompt MUST:
- Start with: "Flat matte [color] wall, soft [direction] light..."
- Describe wall color, light direction, shadow gradient, atmosphere
- End with: "completely empty, no objects, no geometry, flat matte wall, matte finish, no reflections, barely perceptible tonal floor gradient at the bottom"
- Contain zero forbidden words"""

    try:
        logger.info("  [VISUAL EXPERT]   Step 1/2 — Building FLUX prompt via LLM…")
        t_prompt = time.perf_counter()
        response = await llm.ainvoke([
            SystemMessage(content=VISUAL_EXPERT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        elapsed_prompt = time.perf_counter() - t_prompt
        data = json.loads(response.content)
        image_prompt = data.get("image_prompt", "")

        logger.info("  [VISUAL EXPERT]   Prompt ready in %.1fs (%d chars)",
                    elapsed_prompt, len(image_prompt))
        logger.info("  [VISUAL EXPERT]   Prompt preview: %s…", image_prompt[:100])

        logger.info("  [VISUAL EXPERT]   Step 2/2 — Generating image via backend '%s'…",
                    settings.image_backend)
        t_img = time.perf_counter()
        gen_result = await generate_image_from_prompt(image_prompt)
        elapsed_img = time.perf_counter() - t_img

        status = gen_result.get("generation_status", "error")
        model = gen_result.get("generation_model", "—")
        path = gen_result.get("image_path")

        if status == "generated":
            logger.info("  [VISUAL EXPERT] ✓ Image generated in %.1fs | model: %s", elapsed_img, model)
            if path:
                logger.info("  [VISUAL EXPERT]   Saved to: %s", path)
        else:
            logger.warning("  [VISUAL EXPERT] ⚠ Image generation status: %s | model: %s",
                           status, model)

        elapsed_total = time.perf_counter() - t0
        logger.info("  [VISUAL EXPERT] ✓ Done in %.1fs total", elapsed_total)

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
        logger.error("  [VISUAL EXPERT] ✗ Failed after %.1fs — %s", elapsed, e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"visual_expert_error: {e}"]}