"""
Pollinations.ai Image Generator.
Generates images via Pollinations.ai — completely free, no API key.
"""
import logging
import base64
import uuid
import time
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
    logger.info("  [POLLINATIONS]   Image saved: %s", filepath)
    return str(filepath)


async def generate_image_pollinations(prompt: str) -> dict:
    model = settings.pollinations_model
    t0 = time.perf_counter()

    logger.info("  [POLLINATIONS] ▶ Requesting image — model: %s | %dx%d",
                model, settings.image_width, settings.image_height)
    logger.info("  [POLLINATIONS]   Prompt length: %d chars", len(prompt))

    encoded_prompt = quote(prompt)
    url = POLLINATIONS_BASE_URL.format(prompt=encoded_prompt)

    params = {
        "width": settings.image_width,
        "height": settings.image_height,
        "model": model,
        "nologo": "true",
        "enhance": "false",
        "seed": -1,
    }

    try:
        logger.info("  [POLLINATIONS]   Waiting for Pollinations.ai response (up to 120s)…")
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url, params=params)

            if resp.status_code == 429:
                logger.error("  [POLLINATIONS] ✗ Rate limit hit (429). Wait a moment and retry.")
                return {"image_base64": None, "image_path": None,
                        "generation_status": "error", "generation_model": f"pollinations/{model}"}

            resp.raise_for_status()

            img_bytes = resp.content
            content_type = resp.headers.get("content-type", "")
            elapsed = time.perf_counter() - t0

            if len(img_bytes) < 1000 or "image" not in content_type:
                logger.error(
                    "  [POLLINATIONS] ✗ Invalid response. Content-Type: %s | Size: %d bytes",
                    content_type, len(img_bytes))
                return {"image_base64": None, "image_path": None,
                        "generation_status": "error", "generation_model": f"pollinations/{model}"}

            image_path = _save_image(img_bytes)
            img_b64 = base64.b64encode(img_bytes).decode()

            logger.info("  [POLLINATIONS] ✓ Done in %.1fs | Size: %d KB | model: %s",
                        elapsed, len(img_bytes) // 1024, model)

            return {"image_base64": img_b64, "image_path": image_path,
                    "generation_status": "generated", "generation_model": f"pollinations/{model}"}

    except httpx.TimeoutException:
        elapsed = time.perf_counter() - t0
        logger.error("  [POLLINATIONS] ✗ Timeout after %.1fs. Service may be overloaded. Retry.", elapsed)
        return {"image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": f"pollinations/{model}"}
    except httpx.HTTPStatusError as e:
        elapsed = time.perf_counter() - t0
        logger.error("  [POLLINATIONS] ✗ HTTP %s after %.1fs: %s",
                     e.response.status_code, elapsed, e.response.text[:200])
        return {"image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": f"pollinations/{model}"}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error("  [POLLINATIONS] ✗ Unexpected error after %.1fs: %s", elapsed, e)
        return {"image_base64": None, "image_path": None,
                "generation_status": "error", "generation_model": f"pollinations/{model}"}