"""
Coordinator Agent — LangGraph.
Executes copywriter and visual_expert in PARALLEL (fan-out from START),
collects results (fan-in on END) and returns CampaignOutput.
"""
import logging
import time
from langgraph.graph import StateGraph, END, START
from app.agents.state import CampaignState
from app.agents.copywriter import copywriter_node
from app.agents.visual_expert import visual_expert_node
from app.core.schemas import BriefingInput, CampaignOutput, CopyResult, VisualResult
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


async def run_copy(briefing: BriefingInput) -> CopyResult:
    logger.info("▶  COPY ONLY — Campaign started")
    logger.info("   Product      : %s", briefing.product)
    initial_state: CampaignState = {
        "briefing": briefing,
        "copy": None,
        "visual": None,
        "errors": [],
    }
    final_state = await copywriter_node(initial_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning("⚠  COPY ONLY — Completed with %d error(s)", len(errors))
        raise RuntimeError("; ".join(errors))
    copy = final_state.get("copy")
    if copy is None:
        raise RuntimeError("Copy generation failed")
    logger.info("✓  COPY ONLY — Copy generated successfully")
    return copy


async def run_visual(briefing: BriefingInput) -> VisualResult:
    logger.info("▶  VISUAL ONLY — Campaign started")
    logger.info("   Product      : %s", briefing.product)
    initial_state: CampaignState = {
        "briefing": briefing,
        "copy": None,
        "visual": None,
        "errors": [],
    }
    final_state = await visual_expert_node(initial_state)
    errors = final_state.get("errors", [])
    if errors:
        logger.warning("⚠  VISUAL ONLY — Completed with %d error(s)", len(errors))
        raise RuntimeError("; ".join(errors))
    visual = final_state.get("visual")
    if visual is None:
        raise RuntimeError("Visual generation failed")
    logger.info("✓  VISUAL ONLY — Visual generated successfully")
    return visual


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
        logger.info("   Copy    → top_label: '%s'", copy.top_label)
        logger.info("            headline:  '%s'", copy.headline)
        logger.info("            subheadline:  '%s'", copy.subheadline)
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