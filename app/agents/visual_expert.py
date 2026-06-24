"""
Visual Expert Agent — async
1. Costruisce prompt visivo ottimizzato via LLM (gemma4:e4b)
2. Genera l'immagine background via Ollama image generation (async)
"""
import logging
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.core.schemas import VisualResult
from app.agents.state import CampaignState
from app.agents.image_generator import generate_image_from_prompt

logger = logging.getLogger(__name__)

VISUAL_EXPERT_SYSTEM_PROMPT = """You are an Art Director for dermatological and cosmetic advertising, expert in writing optimized prompts for the FLUX image generation model.

YOUR TASK: Write a prompt that generates a completely empty background — a flat matte wall with soft directional light and a barely perceptible floor gradient at the bottom. Nothing else exists in the frame.

WHAT THE IMAGE MUST BE:
A smooth flat matte painted wall lit by soft directional light (from left, right, or diagonal). The light creates gentle feathered shadow transitions across the wall surface. Near the bottom of the frame, a very soft tonal gradient suggests the floor — imperceptible, never a hard line.

ABSOLUTE RULES — never break these:
- Zero objects. Zero props. Zero geometry. Zero 3D shapes.
- No podium, no pedestal, no platform, no riser, no disc, no cylinder.
- No products, no bottles, no jars, no plants, no flowers, no shelves, no furniture.
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

    logger.info("Visual Expert: visual prompt generation started for product '%s'", briefing.product)

    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
        temperature=0.7,
        format="json",
        keep_alive=-1,
    )

    user_prompt = f"""Generate a FLUX image prompt for an empty background wall that fits this campaign briefing.

FORBIDDEN WORDS in the output prompt: "product", "placement", "compositing", "backdrop for", "surface for", "podium", "pedestal", "riser", "platform", "shelf", "object".

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
        response = await llm.ainvoke([
            SystemMessage(content=VISUAL_EXPERT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        data = json.loads(response.content)
        image_prompt = data.get("image_prompt", "")
        logger.info("Visual Expert: prompt built (%d characters)", len(image_prompt))

        # Genera immagine (async)
        gen_result = await generate_image_from_prompt(image_prompt)

        visual_result = VisualResult(
            image_prompt=image_prompt,
            image_base64=gen_result.get("image_base64"),
            image_path=gen_result.get("image_path"),
            generation_status=gen_result.get("generation_status", "error"),
            generation_model=gen_result.get("generation_model"),
        )

        logger.info("Visual Expert: completed with status '%s'", visual_result.generation_status)
        return {**state, "visual": visual_result}

    except Exception as e:
        logger.error("Visual Expert error: %s", e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"visual_expert_error: {e}"]}
