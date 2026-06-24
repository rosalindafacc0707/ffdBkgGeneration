"""
MCP Tool Definitions
"""
from typing import Any
from pydantic import BaseModel


class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


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
            "best house environment": {
                "type": "string",
                "description": "Ambiente domestico ideale (es. soggiorno open space)",
            },
        },
        "required": ["product", "season", "audience", "best house environment"],
    },
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

ALL_TOOLS = [GENERATE_CAMPAIGN_TOOL, GET_IMAGE_TOOL]
