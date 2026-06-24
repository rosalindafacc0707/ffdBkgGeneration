"""
MCP Server endpoint
Espone /mcp/tools (lista tool) e /mcp/call (esecuzione tool).
"""
import logging
import base64
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from app.mcp.tools import ALL_TOOLS
from app.core.schemas import BriefingInput
from app.agents.coordinator import run_campaign

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
    if request.tool_name == "generate_campaign":
        try:
            briefing = BriefingInput(**request.parameters)
            result = await run_campaign(briefing)
            return {"tool_name": request.tool_name, "result": result.model_dump(), "status": "success"}
        except Exception as e:
            logger.error("MCP call error: %s", e)
            raise HTTPException(status_code=500, detail=str(e))

    if request.tool_name == "get_campaign_image":
        image_path = request.parameters.get("image_path")
        if not image_path or not Path(image_path).exists():
            raise HTTPException(status_code=404, detail="Immagine non trovata")
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return {"tool_name": request.tool_name, "image_base64": b64, "status": "success"}

    raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' non trovato")
