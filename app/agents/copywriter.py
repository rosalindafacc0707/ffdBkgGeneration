"""
Copywriter Agent.
Generates headline, tagline and advertising copy from JSON briefing.
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
You create persuasive, emotional, and creative copy for advertising campaigns.
The copy must be concise and impactful, attracting attention and curiosity.
ALWAYS and ONLY respond in this exact JSON format (no text outside the JSON):

{
"headline": "short and impactful main title (max 8 words)",
"tagline": "memorable claim (max 6 words)",
"copy_text": "complete advertising copy with 2-3 evocative sentences that speak to the target audience"
}
"""


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
The copy should always address its objective."""

    try:
        logger.info("  [COPYWRITER]   Calling LLM…")
        response = await llm.ainvoke([
            SystemMessage(content=COPYWRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        elapsed = time.perf_counter() - t0
        data = json.loads(response.content)
        copy_result = CopyResult(
            headline=data.get("headline", ""),
            tagline=data.get("tagline", ""),
            copy_text=data.get("copy_text", ""),
        )
        logger.info("  [COPYWRITER] ✓ Done in %.1fs", elapsed)
        logger.info("  [COPYWRITER]   Headline : %s", copy_result.headline)
        logger.info("  [COPYWRITER]   Tagline  : %s", copy_result.tagline)
        logger.info("  [COPYWRITER]   Copy     : %s…", copy_result.copy_text[:80])
        return {**state, "copy": copy_result}

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("  [COPYWRITER] ✗ Failed after %.1fs — %s", elapsed, e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"copywriter_error: {e}"]}