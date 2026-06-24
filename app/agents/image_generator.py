"""
Image Generator — Router
Smista la generazione immagine al backend configurato in IMAGE_BACKEND (.env):

  "pollinations" → Pollinations.ai (gratuito, no token, default)
  "ollama"       → Ollama locale (no token, richiede modello immagine installato)
  "hf_inference" → HuggingFace Inference API (richiede crediti HF)
  "sdxl"         → SDXL via diffusers locale (~6.5 GB)
  "flux_schnell" → FLUX.1-schnell via diffusers locale (~17 GB)
"""
import logging
import base64
import uuid
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Prefisso negativo fisso preposto ad ogni prompt inviato a FLUX ────────────
# FLUX tende a "completare" scene cosmetiche con podium/prodotti dal suo training.
# Anteporre questi token negativi all'inizio aumenta il loro peso nella
# cross-attention e riduce significativamente le allucinazioni di oggetti.
FLUX_NEGATIVE_PREFIX = (
    "EMPTY WALL ONLY. "
    "Absolutely no podium, no pedestal, no platform, no riser, no cylinder, no disc, "
    "no circular base, no geometric shape, no 3D object, no product, no cosmetic jar, "
    "no bottle, no tube, no container, no prop, no plants, no flower, no leaf, "
    "no shelf, no table, no furniture, no floor object, no shadow of any object, "
    "no hands, no people, no text, no logo, no pattern, no tile, no architectural detail. "
    "The frame contains ONLY a flat matte wall with light and shadow gradients. "
    "Zero objects. Zero props. Zero geometry. Pure empty background. "
)


def _apply_flux_prefix(prompt: str) -> str:
    """Antepone il prefisso negativo al prompt prima dell'invio a FLUX."""
    return FLUX_NEGATIVE_PREFIX + prompt


def _ensure_output_dir() -> Path:
    output_dir = Path(settings.image_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_image(img_b64: str) -> str:
    output_dir = _ensure_output_dir()
    filename = f"background_{uuid.uuid4().hex[:8]}.png"
    filepath = output_dir / filename
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(img_b64))
    logger.info("Image Generator: immagine salvata in '%s'", filepath)
    return str(filepath)


def _is_valid_base64(s: str) -> bool:
    if not s or len(s) < 100:
        return False
    try:
        base64.b64decode(s, validate=True)
        return True
    except Exception:
        return False


async def _generate_via_ollama(prompt: str) -> dict:
    model = settings.ollama_image_model
    logger.info("Image Generator [ollama]: modello '%s'", model)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {
            "width": settings.image_width,
            "height": settings.image_height,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        img_b64 = None
        if _is_valid_base64(data.get("image", "")):
            img_b64 = data["image"]
        elif data.get("images"):
            img_b64 = data["images"][0]
        elif _is_valid_base64(data.get("response", "")):
            img_b64 = data["response"]

        if not img_b64:
            logger.warning("Ollama: nessuna immagine trovata. Campi: %s", list(data.keys()))
            return {
                "image_base64": None,
                "image_path": None,
                "generation_status": "prompt_only",
                "generation_model": model,
            }

        image_path = _save_image(img_b64)
        return {
            "image_base64": img_b64,
            "image_path": image_path,
            "generation_status": "generated",
            "generation_model": model,
        }

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error("Ollama HTTP error %s: %s", e.response.status_code, error_body)
        if "GiB" in error_body or "memory" in error_body.lower():
            logger.error(
                "RAM INSUFFICIENTE per '%s'. Usa IMAGE_BACKEND=pollinations nel .env.", model
            )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": model,
        }
    except Exception as e:
        logger.error("Ollama generator error: %s", e)
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": model,
        }


async def generate_image_from_prompt(prompt: str) -> dict:
    """
    Punto d'ingresso unico. Legge IMAGE_BACKEND dal .env e smista al backend corretto.
    Il prefisso negativo FLUX_NEGATIVE_PREFIX viene anteposto automaticamente
    al prompt per tutti i backend basati su FLUX (pollinations, hf_inference, flux_schnell).
    Ollama e SDXL ricevono il prompt originale.
    """
    backend = settings.image_backend
    logger.info("Image Generator: backend → '%s'", backend)

    if backend == "pollinations":
        flux_prompt = _apply_flux_prefix(prompt)
        logger.debug("Image Generator: prompt con prefisso FLUX applicato")
        from app.agents.pollinations_generator import generate_image_pollinations
        return await generate_image_pollinations(flux_prompt)

    if backend == "hf_inference":
        flux_prompt = _apply_flux_prefix(prompt)
        from app.agents.hf_inference_generator import generate_image_hf_inference
        return await generate_image_hf_inference(flux_prompt)

    if backend == "flux_schnell":
        flux_prompt = _apply_flux_prefix(prompt)
        from app.agents.flux_schnell_generator import generate_image_flux_schnell
        return await generate_image_flux_schnell(flux_prompt)

    if backend == "sdxl":
        # SDXL non è FLUX — non applica il prefisso FLUX
        from app.agents.sdxl_generator import generate_image_sdxl
        return await generate_image_sdxl(prompt)

    # default: ollama
    return await _generate_via_ollama(prompt)