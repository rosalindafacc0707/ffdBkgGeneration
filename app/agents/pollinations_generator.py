"""
Pollinations.ai Image Generator
Genera immagini via Pollinations.ai — completamente gratuito, nessuna API key.

API: GET https://image.pollinations.ai/prompt/{prompt}
Docs: https://pollinations.ai/

Modelli disponibili (parametro ?model=):
  flux        → FLUX.1 (default, qualità alta)
  flux-realism → FLUX.1 orientato al fotorealismo
  flux-anime  → stile anime
  turbo       → più veloce, qualità leggermente inferiore

Nessuna dipendenza aggiuntiva — usa solo httpx (già in requirements.txt).
"""
import logging
import base64
import uuid
from pathlib import Path
from urllib.parse import quote
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt/{prompt}"


def _ensure_output_dir() -> Path:
    output_dir = Path(settings.image_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_image(img_bytes: bytes) -> str:
    output_dir = _ensure_output_dir()
    filename = f"background_{uuid.uuid4().hex[:8]}.png"
    filepath = output_dir / filename
    with open(filepath, "wb") as f:
        f.write(img_bytes)
    logger.info("Pollinations: immagine salvata in '%s'", filepath)
    return str(filepath)


async def generate_image_pollinations(prompt: str) -> dict:
    """
    Chiama Pollinations.ai per generare un'immagine.
    GET https://image.pollinations.ai/prompt/{prompt}?width=...&height=...&model=flux&nologo=true
    Risponde direttamente con i byte dell'immagine (PNG/JPEG).
    """
    model = settings.pollinations_model
    logger.info("Pollinations: avvio generazione con modello '%s'", model)

    encoded_prompt = quote(prompt)
    url = POLLINATIONS_BASE_URL.format(prompt=encoded_prompt)

    params = {
        "width": settings.image_width,
        "height": settings.image_height,
        "model": model,
        "nologo": "true",   # rimuove il watermark pollinations
        "enhance": "false", # non modificare il prompt automaticamente
        "seed": -1,         # seed casuale
    }

    try:
        # Timeout generoso: Pollinations può impiegare 20-40 sec
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 429:
                logger.error(
                    "Pollinations: rate limit temporaneo (429). Riprova tra qualche secondo."
                )
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": f"pollinations/{model}",
                }

            resp.raise_for_status()

            img_bytes = resp.content
            content_type = resp.headers.get("content-type", "")

            # Verifica che sia davvero un'immagine
            if len(img_bytes) < 1000 or "image" not in content_type:
                logger.error(
                    "Pollinations: risposta non valida. "
                    "Content-Type: %s, Size: %d bytes. Body: %s",
                    content_type, len(img_bytes), img_bytes[:200]
                )
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": f"pollinations/{model}",
                }

            image_path = _save_image(img_bytes)
            img_b64 = base64.b64encode(img_bytes).decode()

            logger.info(
                "Pollinations: immagine generata ✓ (%d KB, model=%s)",
                len(img_bytes) // 1024, model
            )
            return {
                "image_base64": img_b64,
                "image_path": image_path,
                "generation_status": "generated",
                "generation_model": f"pollinations/{model}",
            }

    except httpx.TimeoutException:
        logger.error(
            "Pollinations: timeout (120s). Il servizio potrebbe essere sovraccarico. Riprova."
        )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": f"pollinations/{model}",
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            "Pollinations: HTTP error %s: %s",
            e.response.status_code, e.response.text[:300]
        )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": f"pollinations/{model}",
        }
    except Exception as e:
        logger.error("Pollinations: errore inatteso: %s", e)
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": f"pollinations/{model}",
        }
