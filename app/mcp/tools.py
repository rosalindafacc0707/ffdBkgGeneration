"""
MCP Tool Definitions
"""
from typing import Any
from pydantic import BaseModel


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


EXTRACT_BRIEF_TOOL = MCPTool(
    name="extract_brief_from_pdf",
    description=(
        "Estrae un briefing strutturato da un PDF di briefing di campagna. "
        "Restituisce product, season, audience, goal, tone_of_voice e altri insight rilevanti."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pdf_base64": {
                "type": "string",
                "description": "Contenuto del PDF in base64. Il file viene elaborato dal backend.",
            },
            "filename": {
                "type": "string",
                "description": "Nome del file PDF da elaborare, ad esempio briefing.pdf",
            },
        },
        "required": ["pdf_base64", "filename"],
    },
)

GENERATE_CAMPAIGN_TOOL = MCPTool(
    name="generate_campaign",
    description=(
        "Genera copy pubblicitario e immagine di background per una campagna "
        "pubblicitaria partendo da un briefing strutturato. "
        "Restituisce headline, tagline, copy testuale e immagine background PNG."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "product": {"type": "string", "description": "Nome/descrizione del prodotto"},
            "season": {"type": "string", "description": "Stagione o periodo della campagna"},
            "audience": {"type": "string", "description": "Target audience"},
            "goal": {"type": "string", "description": "Obiettivo della campagna"},
            "tone_of_voice": {"type": "string", "description": "Tono della campagna"},
            "brand": {"type": "string", "description": "Brand o azienda"},
            "campaign_name": {"type": "string", "description": "Nome della campagna"},
            "key_messages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Messaggi chiave della campagna",
            },
        },
        "required": ["product", "season", "audience", "goal", "tone_of_voice"],
    },
)

GENERATE_COPY_TOOL = MCPTool(
    name="generate_copy",
    description="Genera solo la parte testuale della campagna (headline, tagline e copy).",
    input_schema=GENERATE_CAMPAIGN_TOOL.input_schema,
)

GENERATE_BACKGROUND_TOOL = MCPTool(
    name="generate_background",
    description="Genera solo l'immagine di background a partire da un briefing strutturato.",
    input_schema=GENERATE_CAMPAIGN_TOOL.input_schema,
)

GET_IMAGE_TOOL = MCPTool(
    name="get_campaign_image",
    description="Recupera l'immagine background generata in formato base64 dato il path del file.",
    input_schema={
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "Path del file immagine restituito da generate_campaign"},
        },
        "required": ["image_path"],
    },
)

HEALTH_TOOL = MCPTool(
    name="health_check",
    description="Restituisce lo stato di salute del servizio backend.",
    input_schema={"type": "object", "properties": {}},
)

ALL_TOOLS = [
    EXTRACT_BRIEF_TOOL,
    GENERATE_CAMPAIGN_TOOL,
    GENERATE_COPY_TOOL,
    GENERATE_BACKGROUND_TOOL,
    GET_IMAGE_TOOL,
    HEALTH_TOOL,
]
