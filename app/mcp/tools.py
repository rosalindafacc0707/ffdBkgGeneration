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
        "Extracts a structured briefing from a campaign briefing PDF. "
        "Returns product, season, audience, goal, tone_of_voice and other relevant insights."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pdf_base64": {
                "type": "string",
                "description": "PDF content in base64. The file is processed by the backend.",
            },
            "filename": {
                "type": "string",
                "description": "Name of the PDF file to process, e.g. briefing.pdf",
            },
        },
        "required": ["pdf_base64", "filename"],
    },
)

GENERATE_CAMPAIGN_TOOL = MCPTool(
    name="generate_campaign",
    description=(
        "Generates advertising copy and background image for an advertising campaign "
        "starting from a structured briefing. "
        "Returns headline, tagline, text copy and background image PNG."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "product": {"type": "string", "description": "Product name/description"},
            "season": {"type": "string", "description": "Campaign season or period"},
            "audience": {"type": "string", "description": "Target audience"},
            "goal": {"type": "string", "description": "Campaign objective"},
            "tone_of_voice": {"type": "string", "description": "Campaign tone"},
            "brand": {"type": "string", "description": "Brand or company"},
            "campaign_name": {"type": "string", "description": "Campaign name"},
            "key_messages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key campaign messages",
            },
        },
        "required": ["product", "season", "audience", "goal", "tone_of_voice"],
    },
)

GENERATE_COPY_TOOL = MCPTool(
    name="generate_copy",
    description="Generates only the text part of the campaign (headline, tagline and copy).",
    input_schema=GENERATE_CAMPAIGN_TOOL.input_schema,
)

GENERATE_BACKGROUND_TOOL = MCPTool(
    name="generate_background",
    description="Generates only the background image starting from a structured briefing.",
    input_schema=GENERATE_CAMPAIGN_TOOL.input_schema,
)

GET_IMAGE_TOOL = MCPTool(
    name="get_campaign_image",
    description="Retrieves the generated background image in base64 format given the file path.",
    input_schema={
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "Path of image file returned by generate_campaign"},
        },
        "required": ["image_path"],
    },
)

HEALTH_TOOL = MCPTool(
    name="health_check",
    description="Returns the health status of the backend service.",
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
