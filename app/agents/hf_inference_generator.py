"""
HuggingFace Inference API Generator
Genera immagini tramite HuggingFace Inference API (free tier).
Nessun download locale, nessun problema di RAM — tutto gira su HF cloud.

Modello raccomandato: black-forest-labs/FLUX.1-dev
→ Supporta negative_prompt nativo — ideale per scene vuote senza oggetti
→ Gratuito su HF Inference API (con HF_TOKEN)
→ Rate limit: ~10-20 req/giorno sul free tier
→ Accettare i termini su: https://huggingface.co/black-forest-labs/FLUX.1-dev

Modello alternativo: black-forest-labs/FLUX.1-schnell
→ Più veloce, meno prompt-following, NO negative_prompt nativo

PREREQUISITI:
1. Account HuggingFace su https://huggingface.co
2. Token READ su https://huggingface.co/settings/tokens
3. HF_TOKEN=hf_xxx nel file .env
4. IMAGE_BACKEND=hf_inference nel file .env
5. HF_INFERENCE_MODEL=black-forest-labs/FLUX.1-dev nel file .env

Dipendenze: solo httpx (già in requirements.txt) — nessuna dipendenza aggiuntiva.
"""
import logging
import base64
import uuid
import asyncio
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

HF_INFERENCE_URL = "https://router.huggingface.co/hf-inference/models/{model}"

# Negative prompt condiviso — applicato a TUTTI i modelli che lo supportano
# FLUX.1-dev lo supporta nativamente; schnell lo ignora silenziosamente
HF_NEGATIVE_PROMPT = (
    "plant, plants, flower, flowers, tree, foliage, greenery, botanical, "
    "podium, pedestal, platform, riser, cylinder, disc, geometric shape, "
    "product, bottle, jar, tube, container, cosmetic, "
    "furniture, chair, stool, table, shelf, desk, sofa, bench, "
    "vase, frame, decoration, prop, ornament, sculpture, "
    "people, person, hands, human, figure, "
    "text, logo, lettering, watermark, "
    "window frame, door, architectural detail, tile, pattern, "
    "reflection, gloss, specular highlight, CGI look, 3D render, "
    "busy background, cluttered, messy"
)

# Modelli che supportano negative_prompt nell'API HF Inference
MODELS_WITH_NEGATIVE_PROMPT = {
    "black-forest-labs/FLUX.1-dev",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "stabilityai/stable-diffusion-2-1",
    "runwayml/stable-diffusion-v1-5",
}


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
    logger.info(" [HF INFERENCE] Image saved: %s", filepath)
    return str(filepath)


def _build_payload(prompt: str, model: str) -> dict:
    parameters: dict = {
        "width": settings.image_width,
        "height": settings.image_height,
    }

    if model in MODELS_WITH_NEGATIVE_PROMPT:
        parameters["negative_prompt"] = HF_NEGATIVE_PROMPT
        logger.info(" [HF INFERENCE] negative_prompt attivo (%d chars)", len(HF_NEGATIVE_PROMPT))

    if "FLUX.1-dev" in model:
        parameters["num_inference_steps"] = 30
        parameters["guidance_scale"] = 3.5

    # Nuovo formato router HF
    return {
        "inputs": prompt,
        "parameters": parameters
    }

async def generate_image_hf_inference(prompt: str) -> dict:
    """
    Chiama HuggingFace Inference API per generare un'immagine.
    Restituisce image_base64, image_path, generation_status, generation_model.
    Gestisce cold start con retry automatico (max 2 tentativi).
    """
    if not settings.hf_token:
        logger.error(
            " [HF INFERENCE] HF_TOKEN mancante nel .env!\n"
            "  1. Genera token READ su https://huggingface.co/settings/tokens\n"
            "  2. Aggiungi HF_TOKEN=hf_xxx nel .env"
        )
        return {
            "image_base64": None, "image_path": None,
            "generation_status": "error", "generation_model": settings.hf_inference_model,
        }

    model = settings.hf_inference_model
    url = HF_INFERENCE_URL.format(model=model)
    headers = {
        "Authorization": f"Bearer {settings.hf_token}",
        "Content-Type": "application/json",
    }
    payload = _build_payload(prompt, model)

    logger.info(" [HF INFERENCE] ▶ Model: '%s' | %dx%d", model, settings.image_width, settings.image_height)
    logger.info(" [HF INFERENCE] Prompt length: %d chars", len(prompt))

    max_retries = 2
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                logger.info(" [HF INFERENCE] Attempt %d/%d — calling API…", attempt, max_retries)
                resp = await client.post(url, headers=headers, json=payload)

                # Cold start → attendi e riprova automaticamente
                if resp.status_code == 503:
                    try:
                        info = resp.json()
                        wait = float(info.get("estimated_time", 20))
                    except Exception:
                        wait = 20.0
                    logger.warning(
                        " [HF INFERENCE] Cold start (503) — attesa %.0fs, poi retry…", wait
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(min(wait, 40))  # aspetta max 40s
                        continue
                    else:
                        logger.error(" [HF INFERENCE] ✗ Modello ancora in cold start dopo retry.")
                        return {
                            "image_base64": None, "image_path": None,
                            "generation_status": "error", "generation_model": model,
                        }

                # Modello gated non autorizzato
                if resp.status_code == 403:
                    logger.error(
                        " [HF INFERENCE] ✗ Accesso negato (403) al modello '%s'.\n"
                        "  → Vai su https://huggingface.co/%s\n"
                        "  → Clicca 'Agree and share my contact information to access this model'",
                        model, model,
                    )
                    return {
                        "image_base64": None, "image_path": None,
                        "generation_status": "error", "generation_model": model,
                    }

                # Rate limit
                if resp.status_code == 429:
                    logger.error(
                        " [HF INFERENCE] ✗ Rate limit (429). "
                        "Free tier: ~10-20 req/giorno. Attendi o usa IMAGE_BACKEND=pollinations."
                    )
                    return {
                        "image_base64": None, "image_path": None,
                        "generation_status": "error", "generation_model": model,
                    }

                resp.raise_for_status()

                # La risposta è binaria (PNG/JPEG diretto)
                img_bytes = resp.content
                if len(img_bytes) < 1000:
                    logger.error(
                        " [HF INFERENCE] ✗ Risposta troppo corta (%d bytes). Body: %s",
                        len(img_bytes), img_bytes[:200]
                    )
                    return {
                        "image_base64": None, "image_path": None,
                        "generation_status": "error", "generation_model": model,
                    }

                image_path = _save_image(img_bytes)
                img_b64 = base64.b64encode(img_bytes).decode()
                logger.info(" [HF INFERENCE] ✓ Immagine generata (%d KB) | model: %s",
                            len(img_bytes) // 1024, model)

                return {
                    "image_base64": img_b64,
                    "image_path": image_path,
                    "generation_status": "generated",
                    "generation_model": model,
                }

        except httpx.TimeoutException:
            logger.error(
                " [HF INFERENCE] ✗ Timeout (180s) al tentativo %d. "
                "Modello in cold start o sovraccarico.", attempt
            )
            if attempt < max_retries:
                logger.info(" [HF INFERENCE] Retry tra 15s…")
                await asyncio.sleep(15)
                continue
            return {
                "image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": model,
            }

        except httpx.HTTPStatusError as e:
            logger.error(" [HF INFERENCE] ✗ HTTP %s: %s",
                         e.response.status_code, e.response.text[:300])
            return {
                "image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": model,
            }

        except Exception as e:
            logger.error(" [HF INFERENCE] ✗ Errore inatteso: %s", e)
            return {
                "image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": model,
            }

    # Fallback finale (non dovrebbe mai arrivare qui)
    return {
        "image_base64": None, "image_path": None,
        "generation_status": "error", "generation_model": model,
    }