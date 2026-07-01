"""
Copywriter Agent.
Generates top_label, headline, subheadline and trust_badges copy from JSON briefing.
Uses ainvoke (async) to enable true parallelization with visual_expert.
"""
import logging
import json
import time
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.core.schemas import CopyResult
from app.agents.state import CampaignState

logger = logging.getLogger(__name__)

COPYWRITER_SYSTEM_PROMPT = """You are a senior advertising copywriter specializing in dermatological products and cosmetics.
Your task is to create high-end, minimalist, and persuasive copy designed specifically for ad creatives, banners, or premium product cards. 

The structure must perfectly fit a visual layout: clean, authoritative, and direct, focusing on immediate impact rather than long storytelling.

ALWAYS and ONLY respond in this exact JSON format (no text outside the JSON). ALWAYS in English language:

{
  "top_label": "Urgency or contextual hook (e.g., 'LIMITED OFFER', 'NEW ARRIVAL', maximum 3 words)",
  "headline": "The main focal point, highly impactful and product-benefit driven (maximum 3 words)",
  "subheadline": "A very short, expert description explaining the product's core action and value proposition (1 clear, elegant short sentence)",
  "trust_badges": [
    "Short trust or origin indicators max 4 words (e.g., 'Formulated by dermatologists', 'Made in France', max 2 items)"
  ]
}"""



async def copywriter_node(state: CampaignState) -> CampaignState:
    """LangGraph node async: copy generation from briefing."""
    briefing = state["briefing"]
    t0 = time.perf_counter()

    logger.info("  [COPYWRITER] ▶ Starting — product: '%s' | model: %s",
                briefing.product, settings.ollama_llm_model)
    logger.info("  [COPYWRITER]   Tone of voice : %s", briefing.tone_of_voice)
    logger.info("  [COPYWRITER]   Audience      : %s", briefing.audience)

    llm = ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_llm_model,
        temperature=0.8,
        format="json",
        keep_alive=-1,
    )

    user_prompt = f"""Create advertising copy for this campaign:

Product: {briefing.product}
Season/Period: {briefing.season}
Audience: {briefing.audience}
Goal: {briefing.goal}
Tone of voice: {briefing.tone_of_voice}
Brand (Optional): {briefing.brand}
Campaign name (Optional): {briefing.campaign_name}
Key messages (Optional): {briefing.key_messages}

The copy should be strongly related to dermatological and cosmetic aspects and speak directly to the audience using the appropriate tone of voice.
The copy should always address its goal and key messages."""

    try:
        logger.info("  [COPYWRITER]   Calling LLM…")
        response = await llm.ainvoke([
            SystemMessage(content=COPYWRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        elapsed = time.perf_counter() - t0
        data = json.loads(response.content)
        copy_result = CopyResult(
            top_label=data.get("top_label", ""),
            headline=data.get("headline", ""),
            subheadline=data.get("subheadline", ""),
            trust_badges=data.get("trust_badges", ""),
        )
        logger.info("  [COPYWRITER] ✓ Done in %.1fs", elapsed)
        logger.info("  [COPYWRITER]   Top Label : %s", copy_result.top_label)
        logger.info("  [COPYWRITER]   Headline  : %s", copy_result.headline)
        logger.info("  [COPYWRITER]   Subheadline     : %s…", copy_result.subheadline)
        logger.info("  [COPYWRITER]   Trust Badges     : %s…", str(copy_result.trust_badges))

        return {**state, "copy": copy_result}

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("  [COPYWRITER] ✗ Failed after %.1fs — %s", elapsed, e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"copywriter_error: {e}"]}