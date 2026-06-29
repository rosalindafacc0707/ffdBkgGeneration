"""
OneDrive Image Selector — Multimodal VLM (gemma4:12b).
Selects the most suitable image from the local OneDrive folder
using Ollama + gemma4:12b as VLM (max ~15 images).
"""
import logging
import base64
import shutil
import time
from pathlib import Path
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _load_images_from_folder(folder: Path) -> tuple[list[str], list[str]]:
    """Loads all images from the folder, returns (filenames, base64_list)."""
    files = sorted([
        f for f in folder.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])
    if not files:
        raise FileNotFoundError(f"No images found in: {folder}")

    filenames = []
    images_b64 = []
    for f in files:
        with open(f, "rb") as img_file:
            images_b64.append(base64.b64encode(img_file.read()).decode("utf-8"))
        filenames.append(f.name)
        logger.info(" [ONEDRIVE SELECTOR] Loaded: %s", f.name)

    return filenames, images_b64


def _copy_selected_to_output(src_path: Path) -> tuple[str, str]:
    """Copies the selected image to output dir, returns (path, base64)."""
    output_dir = Path(settings.image_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / f"selected_{src_path.name}"
    shutil.copy2(src_path, dest)
    with open(dest, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    return str(dest), img_b64


async def select_image_from_onedrive(prompt: str) -> dict:
    """
    Calls gemma4:12b via Ollama to select the most suitable image file
    from the OneDrive folder based on the briefing prompt.
    """
    folder = Path(settings.onedrive_images_dir)
    model = settings.onedrive_vlm_model

    logger.info(" [ONEDRIVE SELECTOR] ▶ Folder: %s | Model: %s", folder, model)

    if not folder.exists():
        logger.error(" [ONEDRIVE SELECTOR] ✗ Folder not found: %s", folder)
        return {
            "image_base64": None, "image_path": None,
            "generation_status": "error", "generation_model": model
        }

    try:
        t0 = time.perf_counter()
        filenames, images_b64 = _load_images_from_folder(folder)
        logger.info(" [ONEDRIVE SELECTOR] %d images loaded", len(filenames))

        # Prompt: images FIRST then text (best practice for gemma4)
        text_prompt = (
            f"Analyze these {len(filenames)} images carefully.\n"
            f"The filenames are (in order): {', '.join(filenames)}\n\n"
            f"The user needs a background image that fits this campaign description:\n"
            f"\"{prompt}\"\n\n"
            "Select the single most suitable image based on mood, color palette, "
            "atmosphere and visual style.\n"
            "Reply with ONLY the filename of the best image, nothing else. "
            "No explanation, no punctuation, just the filename."
        )

        payload = {
            "model": model,
            "prompt": text_prompt,
            "images": images_b64,  # base64 list — images passed directly
            "stream": False,
            "keep_alive": -1,
            "options": {
                "temperature": 0.1,  # low temp for deterministic selection
                "num_predict": 50,   # short response: filename only
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()

        elapsed = time.perf_counter() - t0
        raw_response = data.get("response", "").strip()
        logger.info(
            " [ONEDRIVE SELECTOR] VLM response in %.1fs: '%s'",
            elapsed, raw_response
        )

        # Normalizes: removes spaces, newlines, spurious quotes
        selected_filename = raw_response.strip().strip('"').strip("'").strip()

        # Verify that the file actually exists in the folder
        matched_file = None
        for fname in filenames:
            if fname.lower() == selected_filename.lower():
                matched_file = fname
                break

        # Fallback fuzzy: if model returned a partial name
        if not matched_file:
            for fname in filenames:
                if selected_filename.lower() in fname.lower() or fname.lower() in selected_filename.lower():
                    matched_file = fname
                    logger.warning(
                        " [ONEDRIVE SELECTOR] ⚠ Fuzzy match: '%s' → '%s'",
                        selected_filename, fname
                    )
                    break

        if not matched_file:
            logger.error(
                " [ONEDRIVE SELECTOR] ✗ File not found: '%s'. Available: %s",
                selected_filename, filenames
            )
            # Fallback: use first image
            matched_file = filenames[0]
            logger.warning(
                " [ONEDRIVE SELECTOR] ⚠ Fallback to first image: %s", matched_file
            )

        src_path = folder / matched_file
        output_path, img_b64 = _copy_selected_to_output(src_path)

        logger.info(
            " [ONEDRIVE SELECTOR] ✓ Selected: '%s' → copied to %s",
            matched_file, output_path
        )

        return {
            "image_base64": img_b64,
            "image_path": output_path,
            "generation_status": "selected",
            "generation_model": model,
            "selected_filename": matched_file,
        }

    except FileNotFoundError as e:
        logger.error(" [ONEDRIVE SELECTOR] ✗ %s", e)
        return {
            "image_base64": None, "image_path": None,
            "generation_status": "error", "generation_model": model
        }
    except httpx.HTTPStatusError as e:
        logger.error(
            " [ONEDRIVE SELECTOR] ✗ Ollama HTTP %s: %s",
            e.response.status_code, e.response.text[:200]
        )
        return {
            "image_base64": None, "image_path": None,
            "generation_status": "error", "generation_model": model
        }
    except Exception as e:
        logger.error(" [ONEDRIVE SELECTOR] ✗ Unexpected error: %s", e)
        return {
            "image_base64": None, "image_path": None,
            "generation_status": "error", "generation_model": model
        }