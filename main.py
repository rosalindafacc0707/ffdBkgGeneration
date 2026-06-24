"""
FullForce Ad Generator — Entry Point FastAPI
"""
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.api.routes import router as api_router
from app.mcp.server import router as mcp_router


logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="FullForce Ad Generator",
    description=(
        "Sistema agentico per la generazione di campagne pubblicitarie. "
        "Coordinator → [Copywriter || Visual Expert] → Output per validazione umana."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(mcp_router)

app.mount("/frontend", StaticFiles(directory="frontend", html=True), name="frontend")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level=settings.log_level,
    )