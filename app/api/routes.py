"""
FastAPI Routes — Campaign API
"""
import logging
import base64
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from app.core.schemas import BriefingInput, BriefingJson, CampaignOutput
from app.agents.coordinator import run_campaign
from app.agents.brief_extractor import run_generate_brief_json


# Utils for the service of brief json extraction ---------
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
}
MAX_FILE_SIZE_MB = 10
# ----------------------

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Campaign"])

@router.post(
    "/campaign/brief_insights_extraction",
    response_model=BriefingJson,
    summary="Generate valid JSON from campaign brief",
    description=(
        "Riceve un file PDF di briefing, analizza il contenuto ed estrae un JSON strutturato "
        "con tutti gli insight rilevanti per la generazione dell'asset finale della campagna. "
        "Il JSON restituito può essere usato direttamente come input di /campaign/generate."
    ),
)
async def generate_brief_json(
    file: UploadFile = File(
        ...,
        description="File PDF del briefing di campagna (max 10 MB)",
    )
) -> BriefingJson:
    # Validazione tipo file
    content_type = file.content_type or ""
    filename = file.filename or "unknown.pdf"

    if not filename.lower().endswith(".pdf") and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Formato file non supportato: '{content_type}'. "
                "Carica un file PDF (.pdf)."
            ),
        )

    # Leggi i bytes del file
    pdf_bytes = await file.read()

    # Validazione dimensione
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File troppo grande: {size_mb:.1f} MB. Dimensione massima: {MAX_FILE_SIZE_MB} MB.",
        )

    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Il file caricato è vuoto.")

    logger.info(
        "API brief_insights_extraction: ricevuto '%s' (%.1f MB)", filename, size_mb
    )

    try:
        result = await run_generate_brief_json(pdf_bytes, filename)
        logger.info("API brief_insights_extraction: completato con status OK")
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("API brief_insights_extraction error: %s", e)
        raise HTTPException(status_code=500, detail=f"Errore estrazione brief: {e}")
    

@router.post(
    "/campaign/generate_copy_and_background",
    response_model=CampaignOutput,
    summary="Campaign copy & image background generation",
    description=(
        "Receives a structured JSON briefing and run the agentic system. "
        "The coordinator calls parallely the copywriter and the visual_expert. This last one calls itself the image_generator."
        "At the end the agentic system returns a textual copy and a background image for the final human validation."
    ),
)
async def generate_campaign(briefing: BriefingInput) -> CampaignOutput:
    try:
        logger.info("API: richiesta campagna per prodotto '%s'", briefing.product)
        result = await run_campaign(briefing)
        return result
    except Exception as e:
        logger.error("API error: %s", e)
        raise HTTPException(status_code=500, detail=f"Errore generazione campagna: {e}")


@router.get(
    "/campaign/image/{filename}",
    summary="Scarica immagine background generata",
    description="Restituisce il file PNG del background generato.",
)
async def get_image(filename: str):
    from app.core.config import settings
    filepath = Path(settings.image_output_dir) / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Immagine non trovata")
    return FileResponse(str(filepath), media_type="image/png", filename=filename)



@router.get("/health", summary="Health check")
async def health():
    return {"status": "ok", "service": "FullForce Ad Generator"}
