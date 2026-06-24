"""
HuggingFace Inference API Generator
Genera immagini tramite HuggingFace Inference API (free tier).
Nessun download locale, nessun problema di RAM — tutto gira su HF cloud.

Modello default: black-forest-labs/FLUX.1-schnell
  → gratuito su HF Inference API (con HF_TOKEN)
  → rate limit: ~10-20 req/giorno sul free tier

Modello alternativo: stabilityai/stable-diffusion-xl-base-1.0
  → più permissivo sui rate limit

PREREQUISITI:
  1. Account HuggingFace su https://huggingface.co
  2. Token READ su https://huggingface.co/settings/tokens
  3. HF_TOKEN=hf_xxx nel file .env
  4. IMAGE_BACKEND=hf_inference nel file .env

  Per FLUX.1-schnell devi anche accettare i termini:
  https://huggingface.co/black-forest-labs/FLUX.1-schnell
  → clicca "Agree and share my contact information to access this model"

Dipendenze: solo httpx (già in requirements.txt) — nessuna dipendenza aggiuntiva.
"""
import logging
import base64
import uuid
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"


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
    logger.info("HF Inference: immagine salvata in '%s'", filepath)
    return str(filepath)


async def generate_image_hf_inference(prompt: str) -> dict:
    """
    Chiama HuggingFace Inference API per generare un'immagine.
    Restituisce image_base64, image_path, generation_status, generation_model.
    """
    if not settings.hf_token:
        logger.error(
            "HF Inference: HF_TOKEN mancante nel .env!\n"
            "  1. Genera token READ su https://huggingface.co/settings/tokens\n"
            "  2. Aggiungi HF_TOKEN=hf_xxx nel .env"
        )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": settings.hf_inference_model,
        }

    model = settings.hf_inference_model
    url = HF_INFERENCE_URL.format(model=model)
    logger.info("HF Inference: avvio generazione con modello '%s'", model)

    headers = {
        "Authorization": f"Bearer {settings.hf_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": prompt,
        "parameters": {
            "width": settings.image_width,
            "height": settings.image_height,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

            # Modello in cold start → 503 con estimated_time
            if resp.status_code == 503:
                try:
                    info = resp.json()
                    wait = info.get("estimated_time", "?")
                    logger.warning(
                        "HF Inference: modello in avvio (cold start), "
                        "attesa stimata %s sec. Riprova tra poco.", wait
                    )
                except Exception:
                    pass
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": model,
                }

            # Modello gated non autorizzato
            if resp.status_code == 403:
                logger.error(
                    "HF Inference: accesso negato (403) al modello '%s'.\n"
                    "  Vai su https://huggingface.co/%s\n"
                    "  e clicca 'Agree and share my contact information to access this model'",
                    model, model,
                )
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": model,
                }

            # Rate limit superato
            if resp.status_code == 429:
                logger.error(
                    "HF Inference: rate limit raggiunto (429). "
                    "Il free tier permette ~10-20 richieste/giorno. "
                    "Attendi o cambia HF_INFERENCE_MODEL con un modello meno restrittivo."
                )
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": model,
                }

            resp.raise_for_status()

            # La risposta è binaria (PNG/JPEG diretto)
            img_bytes = resp.content
            if len(img_bytes) < 1000:
                logger.error(
                    "HF Inference: risposta troppo corta (%d bytes), probabile errore. "
                    "Body: %s", len(img_bytes), img_bytes[:200]
                )
                return {
                    "image_base64": None,
                    "image_path": None,
                    "generation_status": "error",
                    "generation_model": model,
                }

            image_path = _save_image(img_bytes)
            img_b64 = base64.b64encode(img_bytes).decode()

            logger.info(
                "HF Inference: immagine generata ✓ (%d KB)", len(img_bytes) // 1024
            )
            return {
                "image_base64": img_b64,
                "image_path": image_path,
                "generation_status": "generated",
                "generation_model": model,
            }

    except httpx.TimeoutException:
        logger.error(
            "HF Inference: timeout (120s). Il modello è probabilmente in cold start. "
            "Riprova tra 20-30 secondi."
        )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": model,
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            "HF Inference: HTTP error %s: %s",
            e.response.status_code, e.response.text[:300]
        )
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": model,
        }
    except Exception as e:
        logger.error("HF Inference: errore inatteso: %s", e)
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": model,
        }
