"""
Coordinator Agent — LangGraph
Esegue copywriter e visual_expert in PARALLELO (fan-out da START),
raccoglie i risultati (fan-in su END) e restituisce CampaignOutput.
"""
import logging
from langgraph.graph import StateGraph, END, START
from app.agents.state import CampaignState
from app.agents.copywriter import copywriter_node
from app.agents.visual_expert import visual_expert_node
from app.core.schemas import BriefingInput, CampaignOutput
from app.core.config import settings
logger = logging.getLogger(__name__)


def build_parallel_graph():
    """
    Grafo con vera esecuzione parallela.
    START → [copywriter, visual_expert] → END
    Il merge dei risultati è gestito dalle funzioni Annotated in CampaignState.
    """
    graph = StateGraph(CampaignState)

    graph.add_node("copywriter", copywriter_node)
    graph.add_node("visual_expert", visual_expert_node)

    # Fan-out: START esegue entrambi i nodi in parallelo
    graph.add_edge(START, "copywriter")
    graph.add_edge(START, "visual_expert")

    # Fan-in: entrambi convergono su END
    graph.add_edge("copywriter", END)
    graph.add_edge("visual_expert", END)

    return graph.compile()


async def run_campaign(briefing: BriefingInput) -> CampaignOutput:
    """
    Punto d'ingresso principale.
    Esegue il grafo in parallelo e restituisce CampaignOutput.
    """
    logger.info("Coordinator: campaign started fro the product: '%s'", briefing.product)

    copy_generation_model = settings.ollama_llm_model
    visual_model = settings.ollama_vision_model
    image_generation_model = settings.ollama_image_model
    #logger.info("Coordinator: models chosen -> Copy Creation: '%s'", copy_generation_model, " - Visual: '%s'", visual_model, " - Text-to-Image: '%s'", image_generation_model)

    compiled = build_parallel_graph()

    initial_state: CampaignState = {
        "briefing": briefing,
        "copy":     None,
        "visual":   None,
        "errors":   [],
    }

    final_state = await compiled.ainvoke(initial_state)

    errors = final_state.get("errors", [])
    logger.info("Coordinator: generation complete, errors: %s", errors)

    return CampaignOutput(
        briefing=briefing,
        copy=final_state["copy"],
        visual=final_state["visual"],
        status="completed" if not errors else "completed_with_errors",
    )
