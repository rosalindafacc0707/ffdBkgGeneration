"""
MCP Server endpoint.
Exposes /mcp/tools (tool list) and /mcp/call (tool execution).
"""
import base64
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.brief_extractor import run_generate_brief_json
from app.agents.coordinator import run_campaign, run_copy, run_visual
from app.core.schemas import BriefingInput
from app.mcp.tools import ALL_TOOLS
from app.mcp.workfront_mock import get_ready_briefings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])


class MCPCallRequest(BaseModel):
    tool_name: str
    parameters: dict[str, Any]


@router.get("/tools")
async def list_tools():
    return {"tools": [t.model_dump() for t in ALL_TOOLS]}


@router.post("/call")
async def call_tool(request: MCPCallRequest):
    try:
        if request.tool_name == "extract_brief_from_pdf":
            pdf_base64 = request.parameters.get("pdf_base64")
            filename = request.parameters.get("filename") or "briefing.pdf"
            if not pdf_base64:
                raise HTTPException(status_code=400, detail="pdf_base64 is required")

            pdf_bytes = base64.b64decode(pdf_base64)
            result = await run_generate_brief_json(pdf_bytes, filename)
            return {"tool_name": request.tool_name, "result": result.model_dump(), "status": "success"}

        if request.tool_name == "generate_campaign":
            briefing = BriefingInput(**request.parameters)
            result = await run_campaign(briefing)
            return {"tool_name": request.tool_name, "result": result.model_dump(), "status": "success"}

        if request.tool_name == "generate_copy":
            briefing = BriefingInput(**request.parameters)
            result = await run_copy(briefing)
            return {"tool_name": request.tool_name, "result": result, "status": "success"}

        if request.tool_name == "generate_background":
            briefing = BriefingInput(**request.parameters)
            result = await run_visual(briefing)
            return {"tool_name": request.tool_name, "result": result, "status": "success"}

        if request.tool_name == "get_campaign_image":
            image_path = request.parameters.get("image_path")
            if not image_path or not Path(image_path).exists():
                raise HTTPException(status_code=404, detail="Immagine non trovata")
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return {"tool_name": request.tool_name, "image_base64": b64, "status": "success"}

        if request.tool_name == "health_check":
            return {"tool_name": request.tool_name, "status": "ok", "service": "FullForce Ad Generator"}

        if request.tool_name == "get_ready_briefings":
            limit = request.parameters.get("limit", 5)
            project_id = request.parameters.get("project_id")
            result = await get_ready_briefings(limit=limit, project_id=project_id)
            return {"tool_name": request.tool_name, "result": result, "status": "success"}

        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' non trovato")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MCP call error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
