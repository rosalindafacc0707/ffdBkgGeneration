"""
Image Generator — Router
Smista la generazione immagine al backend configurato in IMAGE_BACKEND (.env).
"""
import logging
import base64
import uuid
import time
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

FLUX_NEGATIVE_PREFIX = (
    "EMPTY WALL ONLY. "
    "Absolutely no podium, no pedestal, no platform, no riser, no cylinder, no disc, "
    "no circular base, no geometric shape, no 3D object, no product, no cosmetic jar, "
    "no bottle, no tube, no container, no prop, no plants, no plant, no flowers, no flower, no leaf, no leaves, no greenery, no foliage, no botanical, "
    "no shelf, no table, no furniture, no floor object, no shadow of any object, "
    "no hands, no people, no text, no logo, no pattern, no tile, no architectural detail. "
    "The frame contains ONLY a flat matte wall with light and shadow gradients. "
    "Zero objects. Zero props. Zero geometry. Pure empty background. "
)


def _apply_flux_prefix(prompt: str) -> str:
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
    logger.info("  [IMAGE ROUTER]   Saved: %s", filepath)
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
    logger.info("  [IMAGE ROUTER]   Ollama image model: %s", model)
    logger.info("  [IMAGE ROUTER]   Resolution: %dx%d", settings.image_width, settings.image_height)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"width": settings.image_width, "height": settings.image_height},
    }

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(f"{settings.ollama_base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        elapsed = time.perf_counter() - t0

        img_b64 = None
        if _is_valid_base64(data.get("image", "")):
            img_b64 = data["image"]
        elif data.get("images"):
            img_b64 = data["images"][0]
        elif _is_valid_base64(data.get("response", "")):
            img_b64 = data["response"]

        if not img_b64:
            logger.warning("  [IMAGE ROUTER] ⚠ No image in Ollama response after %.1fs. Fields: %s",
                           elapsed, list(data.keys()))
            return {"image_base64": None, "image_path": None,
                    "generation_status": "prompt_only", "generation_model": model}

        image_path = _save_image(img_b64)
        logger.info("  [IMAGE ROUTER] ✓ Ollama image generated in %.1fs", elapsed)
        return {"image_base64": img_b64, "image_path": image_path,
                "generation_status": "generated", "generation_model": model}

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error("  [IMAGE ROUTER] ✗ Ollama HTTP %s: %s", e.response.status_code, error_body[:200])
        if "GiB" in error_body or "memory" in error_body.lower():
            logger.error("  [IMAGE ROUTER]   Insufficient RAM for '%s'. Try IMAGE_BACKEND=pollinations", model)
        return {"image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": model}
    except Exception as e:
        logger.error("  [IMAGE ROUTER] ✗ Ollama error: %s", e)
        return {"image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": model}


async def generate_image_from_prompt(prompt: str) -> dict:
    backend = settings.image_backend
    logger.info("  [IMAGE ROUTER] ▶ Backend: '%s' | Resolution: %dx%d",
                backend, settings.image_width, settings.image_height)

    if backend == "pollinations":
        flux_prompt = _apply_flux_prefix(prompt)
        logger.info("  [IMAGE ROUTER]   FLUX negative prefix applied (%d chars total)", len(flux_prompt))
        from app.agents.pollinations_generator import generate_image_pollinations
        return await generate_image_pollinations(flux_prompt)

    if backend == "hf_inference":
        flux_prompt = _apply_flux_prefix(prompt)
        logger.info("  [IMAGE ROUTER]   FLUX negative prefix applied")
        from app.agents.hf_inference_generator import generate_image_hf_inference
        return await generate_image_hf_inference(flux_prompt)

    if backend == "flux_schnell":
        flux_prompt = _apply_flux_prefix(prompt)
        logger.info("  [IMAGE ROUTER]   FLUX negative prefix applied")
        from app.agents.flux_schnell_generator import generate_image_flux_schnell
        return await generate_image_flux_schnell(flux_prompt)

    if backend == "sdxl":
        logger.info("  [IMAGE ROUTER]   SDXL — no FLUX prefix applied")
        from app.agents.sdxl_generator import generate_image_sdxl
        return await generate_image_sdxl(prompt)

    # default: ollama
    return await _generate_via_ollama(prompt)