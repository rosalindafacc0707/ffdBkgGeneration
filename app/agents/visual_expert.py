"""
Visual Expert Agent — async.
1. Constructs optimized visual prompt via LLM
2. Generates background image via image_generator (async)
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

VISUAL_EXPERT_SYSTEM_PROMPT = """Act as a master of architectural minimalism and studio photography. Your absolute priority is formal purity. When generating a scene, your goal is to eliminate everything non-essential, leaving only pure geometric forms and clean material textures. Do not add any props, plants, decorations, furniture, or extraneous elements under any circumstances. Focus exclusively on the wall texture, light angles, and clean geometry. Use soft ambient gradients to provide depth instead of physical objects or cast shadows. Ensure the scene is completely pristine, uniform, and empty.

YOUR TASK: Write a hyper-realistic, ultra-minimalist studio photography prompt for FLUX that depicts ONLY the seamless intersection of a flat floor and a vertical background wall — an infinity cove. The image must be completely vacant — no objects, no props, no decorations of any kind.

WHAT THE IMAGE MUST BE:
A smooth, seamless matte wall curving into a clean floor — a classic photography infinity cove (cyclorama). The texture must be matte and tactile, like fine plaster or limewash. Light is soft, warm, and diffused — coming gently from one side — creating a subtle gradient across the wall. The floor is slightly lighter in tone. There are NO cast shadows from any external source, NO window shapes, NO grid patterns, NO geometric shadow lines on the wall. Depth is created ONLY through tonal gradient and soft ambient falloff.

ABSOLUTE RULES — never break these:
- Zero objects. Zero props. Zero geometry other than the wall-floor seamless curve.
- No podium, no pedestal, no platform, no riser, no disc, no cylinder, no shelf.
- No products, no bottles, no jars, no plants, no flowers, no greenery, no foliage, no decorations.
- No people, no hands, no text, no logos, no patterns, no tiles.
- No reflections, no specular highlights, no gloss, no CGI look.
- NO window shadows, NO blind shadows, NO grid shadows, NO slatted shadows, NO geometric shadow patterns of any kind.
- Do NOT use these words in the output: "product", "placement", "compositing", "surface for", "backdrop for", "window", "blind", "slat", "grid shadow".

LIGHT: Soft, warm, diffused ambient light from one side. Light fades naturally across the wall creating a gentle gradient. NO sharp shadows. NO geometric cast shadows. Depth comes from tonal falloff only.

STRICT BRAND PALETTE — use ONLY these colors, no exceptions:
Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37
Emerald #1C3934 · Noir #131315 · Espresso #241515
Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

Choose ONE dominant wall/floor color from the palette, optionally ONE secondary color for tonal depth.

PROMPT FORMAT:
- Start with: "A hyper-realistic, ultra-minimalist studio photograph of an empty infinity cove interior."
- Describe: wall/floor color and texture, light direction and soft gradient behavior, seamless floor-wall curve
- Minimum 70 words, in English
- Always end with: "Strictly no objects, no props, no plants, no furniture, no decorations, no window shadows, no geometric shadows. The space is completely vacant. Matte finish, no reflections, no gloss."

Respond ONLY in this JSON format:
{
  "image_prompt": "prompt in english"
}
"""


async def visual_expert_node(state: CampaignState) -> CampaignState:
    """LangGraph node async: generates visual prompt + background image."""
    briefing = state["briefing"]
    t0 = time.perf_counter()

    logger.info(" [VISUAL EXPERT] ▶ Starting — product: '%s' | vision model: %s",
                briefing.product, settings.ollama_vision_model)
    logger.info(" [VISUAL EXPERT] Season : %s | Goal: %s",
                briefing.season, briefing.goal[:60] if briefing.goal else "—")

    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
        temperature=0.7,
        format="json",
        keep_alive=-1,
    )

    user_prompt = f"""Generate a FLUX image prompt for a completely empty minimalist studio background that fits this campaign briefing in terms of color mood and atmosphere.

FORBIDDEN WORDS in the output prompt: "product", "placement", "compositing", "backdrop for", "surface for", "podium", "pedestal", "riser", "platform", "shelf", "footrest", "lift", "object", "plant", "plants", "flower", "flowers", "greenery", "foliage", "botanical", "table", "chair", "furniture", "decoration", "vase", "frame".

Choose the most evocative wall/floor color and light direction for this product and season.
Use ONLY brand palette colors: Blush #F9EDEF · Champagne #E5C8B6 · Cognac #C3955A · Amber #BA6A37 · Emerald #1C3934 · Noir #131315 · Espresso #241515 · Cappuccino #EBEAE0 · Cream #F3F2EB · Flat White #F9F9F9

A diagonal shadow from a window grid or slatted blinds is ENCOURAGED if it suits the season and mood — it adds drama without objects.

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
- Start with: "A hyper-realistic, ultra-minimalist studio photograph of an empty interior space."
- Describe wall/floor color and texture (matte, plaster-like), light direction, shadow behavior
- Optionally describe a sharp clean diagonal shadow from window grid/slatted blinds
- End with: "Strictly no objects, no props, no plants, no furniture, no decorations. The space is completely vacant. Matte finish, no reflections, no gloss."
- Contain zero forbidden words
- Be minimum 70 words in English"""

    try:
        logger.info(" [VISUAL EXPERT] Step 1/2 — Building FLUX prompt via LLM…")
        t_prompt = time.perf_counter()
        response = await llm.ainvoke([
            SystemMessage(content=VISUAL_EXPERT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        elapsed_prompt = time.perf_counter() - t_prompt
        data = json.loads(response.content)
        image_prompt = data.get("image_prompt", "")

        logger.info(" [VISUAL EXPERT] Prompt ready in %.1fs (%d chars)",
                    elapsed_prompt, len(image_prompt))
        logger.info(" [VISUAL EXPERT] Prompt preview: %s…", image_prompt[:100])

        logger.info(" [VISUAL EXPERT] Step 2/2 — Generating image via backend '%s'…",
                    settings.image_backend)
        t_img = time.perf_counter()
        gen_result = await generate_image_from_prompt(image_prompt)
        elapsed_img = time.perf_counter() - t_img

        status = gen_result.get("generation_status", "error")
        model = gen_result.get("generation_model", "—")
        path = gen_result.get("image_path")

        if status == "generated":
            logger.info(" [VISUAL EXPERT] ✓ Image generated in %.1fs | model: %s", elapsed_img, model)
            if path:
                logger.info(" [VISUAL EXPERT] Saved to: %s", path)
        else:
            logger.warning(" [VISUAL EXPERT] ⚠ Image generation status: %s | model: %s",
                           status, model)

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