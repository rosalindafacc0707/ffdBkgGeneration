"""
Coordinator Agent — LangGraph
Esegue copywriter e visual_expert in PARALLELO (fan-out da START),
raccoglie i risultati (fan-in su END) e restituisce CampaignOutput.
"""
import logging
import time
from langgraph.graph import StateGraph, END, START
from app.agents.state import CampaignState
from app.agents.copywriter import copywriter_node
from app.agents.visual_expert import visual_expert_node
from app.core.schemas import BriefingInput, CampaignOutput
from app.core.config import settings

logger = logging.getLogger(__name__)

SEPARATOR = "─" * 60


def build_parallel_graph():
    graph = StateGraph(CampaignState)
    graph.add_node("copywriter", copywriter_node)
    graph.add_node("visual_expert", visual_expert_node)
    graph.add_edge(START, "copywriter")
    graph.add_edge(START, "visual_expert")
    graph.add_edge("copywriter", END)
    graph.add_edge("visual_expert", END)
    return graph.compile()


async def run_campaign(briefing: BriefingInput) -> CampaignOutput:
    t0 = time.perf_counter()

    logger.info(SEPARATOR)
    logger.info("▶  COORDINATOR — Campaign started")
    logger.info("   Product      : %s", briefing.product)
    logger.info("   Season       : %s", briefing.season)
    logger.info("   Audience     : %s", briefing.audience)
    logger.info("   Brand        : %s", briefing.brand or "—")
    logger.info("   Campaign     : %s", briefing.campaign_name or "—")
    logger.info("   Copy model   : %s", settings.ollama_llm_model)
    logger.info("   Vision model : %s", settings.ollama_vision_model)
    logger.info("   Image backend: %s", settings.image_backend)
    logger.info(SEPARATOR)
    logger.info("⇉  Launching COPYWRITER and VISUAL EXPERT in parallel…")

    compiled = build_parallel_graph()

    initial_state: CampaignState = {
        "briefing": briefing,
        "copy":     None,
        "visual":   None,
        "errors":   [],
    }

    final_state = await compiled.ainvoke(initial_state)

    elapsed = time.perf_counter() - t0
    errors = final_state.get("errors", [])

    logger.info(SEPARATOR)
    if errors:
        logger.warning("⚠  COORDINATOR — Completed with %d error(s) in %.1fs", len(errors), elapsed)
        for err in errors:
            logger.warning("   • %s", err)
    else:
        logger.info("✓  COORDINATOR — All agents completed successfully in %.1fs", elapsed)

    copy = final_state.get("copy")
    visual = final_state.get("visual")

    if copy:
        logger.info("   Copy    → headline: '%s'", copy.headline)
        logger.info("            tagline:  '%s'", copy.tagline)
    if visual:
        logger.info("   Visual  → status: %s | model: %s",
                    visual.generation_status, visual.generation_model)
        if visual.image_path:
            logger.info("            path:   %s", visual.image_path)

    logger.info(SEPARATOR)

    status = "completed" if not errors else "completed_with_errors"
    return CampaignOutput(
        briefing=briefing,
        copy=copy,
        visual=visual,
        status=status,
    )