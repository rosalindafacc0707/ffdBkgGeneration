"""
Copywriter Agent
Genera headline, tagline e copy pubblicitario dal briefing JSON.
Usa ainvoke (async) per permettere vera parallelizzazione con visual_expert.
"""
import logging
import json
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
    logger.info("Copywriter: copy generation in progress for the product '%s'", briefing.product)

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
        response = await llm.ainvoke([
            SystemMessage(content=COPYWRITER_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])
        data = json.loads(response.content)
        copy_result = CopyResult(
            headline=data.get("headline", ""),
            tagline=data.get("tagline", ""),
            copy_text=data.get("copy_text", ""),
        )
        logger.info("Copywriter: copy successfully generated")
        return {**state, "copy": copy_result}

    except Exception as e:
        logger.error("Copywriter error: %s", e)
        errors = state.get("errors", [])
        return {**state, "errors": errors + [f"copywriter_error: {e}"]}
