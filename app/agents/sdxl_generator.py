"""
SDXL Generator
Genera immagini in locale usando Stable Diffusion XL Base 1.0 via HuggingFace diffusers.
Ottimizzato per Mac Apple Silicon (MPS) e sistemi con 16 GB di memoria.

Vantaggi rispetto a FLUX.1-schnell:
  - Peso modello: ~6.5 GB (vs ~17 GB di FLUX) → non satura i 16 GB di RAM unificata
  - Nessun gate HuggingFace, nessun token necessario
  - Qualità ottima per background editoriali/studio
  - Stessa API diffusers, configurazione identica

PREREQUISITI:
  - pip install -r requirements-flux.txt
  - Prima esecuzione: scarica automaticamente ~6.5 GB in ~/.cache/huggingface
    oppure usa: python download_sdxl_model.py
"""
import logging
import base64
import uuid
import io
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"

_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    logger.info("SDXL: caricamento pipeline '%s'...", MODEL_ID)

    try:
        import torch
        from diffusers import StableDiffusionXLPipeline

        # Prova prima dalla cache locale (nessuna rete)
        try:
            pipe = StableDiffusionXLPipeline.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16",
                local_files_only=True,
            )
            logger.info("SDXL: modello caricato dalla cache locale")
        except Exception:
            # Cache vuota: scarica (~6.5 GB, nessun token necessario)
            logger.info("SDXL: download modello (~6.5 GB)... attendere")
            pipe = StableDiffusionXLPipeline.from_pretrained(
                MODEL_ID,
                torch_dtype=torch.float16,
                use_safetensors=True,
                variant="fp16",
            )
            logger.info("SDXL: download completato")

        # Ottimizzazioni memoria — fondamentali su 16 GB
        pipe.enable_attention_slicing()          # riduce picchi di RAM durante l'inferenza
        pipe.enable_vae_slicing()                # decodifica VAE a slice per risparmiare memoria

        if torch.backends.mps.is_available():
            pipe = pipe.to("mps")
            # Su MPS, enable_model_cpu_offload non è supportato:
            # attention_slicing + vae_slicing sono sufficienti
            logger.info("SDXL: backend MPS (Apple Silicon) attivo")
        elif torch.cuda.is_available():
            pipe.enable_model_cpu_offload()      # su CUDA: offload layers non usati su CPU
            logger.info("SDXL: backend CUDA attivo con CPU offload")
        else:
            logger.warning("SDXL: nessuna GPU disponibile, uso CPU (molto lento)")

        _pipeline = pipe
        logger.info("SDXL: pipeline pronta")
        return _pipeline

    except ImportError as e:
        logger.error("SDXL: dipendenze mancanti -> pip install -r requirements-flux.txt\n%s", e)
        raise
    except Exception as e:
        logger.error("SDXL: errore caricamento pipeline: %s", e)
        raise


def _ensure_output_dir() -> Path:
    output_dir = Path(settings.image_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def generate_image_sdxl(prompt: str) -> dict:
    import asyncio

    logger.info("SDXL: avvio generazione immagine")

    def _generate_sync():
        pipe = _get_pipeline()
        result = pipe(
            prompt=prompt,
            negative_prompt=(
                "people, hands, human elements, products, packaging, text, logos, "
                "plants, towels, bottles, props, decorative elements, heavy textures, "
                "visual noise, blurry, low quality, oversaturated, harsh shadows, "
                "hyper-realistic, CGI look, shiny surfaces, glossy"
            ),
            width=settings.image_width,
            height=settings.image_height,
            num_inference_steps=settings.sdxl_num_inference_steps,
            guidance_scale=settings.sdxl_guidance_scale,
        )
        return result.images[0]

    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, _generate_sync)

        output_dir = _ensure_output_dir()
        filename = f"background_{uuid.uuid4().hex[:8]}.png"
        filepath = output_dir / filename
        image.save(str(filepath))
        logger.info("SDXL: immagine salvata in '%s'", filepath)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "image_base64": img_b64,
            "image_path": str(filepath),
            "generation_status": "generated",
            "generation_model": MODEL_ID,
        }

    except Exception as e:
        logger.error("SDXL: errore generazione: %s", e)
        return {
            "image_base64": None,
            "image_path": None,
            "generation_status": "error",
            "generation_model": MODEL_ID,
        }
