"""
Flux Schnell Generator
Genera immagini in locale usando FLUX.1-schnell via HuggingFace diffusers.
Ottimizzato per Mac Apple Silicon tramite backend MPS (Metal Performance Shaders).

PREREQUISITI:
  1. Account HuggingFace + termini accettati su:
     https://huggingface.co/black-forest-labs/FLUX.1-schnell
     → clicca "Agree and access repository"
  2. Token Fine-grained con permesso "Read access to contents of all public gated repos"
     su: https://huggingface.co/settings/tokens
  3. HF_TOKEN=hf_xxx nel file .env
  4. Download modello una-tantum (PRIMA di avviare l'app):
     python download_flux_model.py
"""
import logging
import base64
import uuid
import io
import os
from pathlib import Path
from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_ID = "black-forest-labs/FLUX.1-schnell"
MODEL_PAGE = "https://huggingface.co/black-forest-labs/FLUX.1-schnell"
TOKENS_PAGE = "https://huggingface.co/settings/tokens"

_pipeline = None


def _validate_hf_token():
    if not settings.hf_token:
        raise ValueError(
            "HF_TOKEN mancante nel file .env!\n"
            f"  1. Genera token Fine-grained su: {TOKENS_PAGE}\n"
            f"  2. Accetta i termini su: {MODEL_PAGE}\n"
            "  3. Aggiungi HF_TOKEN=hf_tuotoken nel .env"
        )


_GATED_403_MSG = (
    f"\n{'='*60}\n"
    "ACCESSO NEGATO (403 Forbidden).\n"
    "Il token HuggingFace e' valido, ma NON hai ancora accettato\n"
    "i termini d'uso del modello FLUX.1-schnell.\n\n"
    "SOLUZIONE (2 minuti):\n"
    f"  1. Vai su: {MODEL_PAGE}\n"
    "     Assicurati di essere loggato con l'account legato al tuo HF_TOKEN\n"
    "  2. Clicca il pulsante 'Agree and access repository'\n"
    "  3. Riavvia il servizio\n"
    f"{'='*60}"
)


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    _validate_hf_token()
    token = settings.hf_token

    os.environ["HF_TOKEN"] = token
    os.environ["HUGGING_FACE_HUB_TOKEN"] = token

    logger.info("Flux Schnell: caricamento pipeline '%s'...", MODEL_ID)

    try:
        import torch
        from diffusers import FluxPipeline
        from huggingface_hub import login, HfApi, hf_hub_download, snapshot_download

        login(token=token, add_to_git_credential=False)
        logger.info("Flux Schnell: token scritto nella cache huggingface_hub")

        # Verifica accesso con file piccolo (evita download parziali con 403)
        try:
            hf_hub_download(repo_id=MODEL_ID, filename="model_index.json", token=token)
            logger.info("Flux Schnell: accesso ai file del modello verificato")
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e) or "gated" in str(e).lower():
                raise PermissionError(_GATED_403_MSG) from e
            raise

        # Strategia cache-first:
        # 1. Prova cache locale senza toccare la rete (instantaneo se gia' scaricato).
        # 2. Se mancante, avverte e avvia il download con max_workers=1
        #    per evitare il crash "Background writer channel closed" che si verifica
        #    scrivendo piu' file da GB in parallelo dentro un request handler.
        #
        # RACCOMANDATO: eseguire "python download_flux_model.py" una volta
        # prima di avviare l'app per un download controllato e resumabile.

        try:
            logger.info("Flux Schnell: ricerca modello nella cache locale...")
            local_model_dir = snapshot_download(
                repo_id=MODEL_ID,
                token=token,
                local_files_only=True,
            )
            logger.info("Flux Schnell: modello trovato in cache -> '%s'", local_model_dir)
        except Exception:
            logger.warning(
                "Flux Schnell: modello non in cache locale. "
                "CONSIGLIO: interrompi l'app e scarica il modello separatamente con: "
                "python download_flux_model.py  "
                "Il download (~17-57 GB) avviato da qui potrebbe crashare per timeout."
            )
            try:
                local_model_dir = snapshot_download(
                    repo_id=MODEL_ID,
                    token=token,
                    ignore_patterns=["*.msgpack", "*.h5", "flax_model*", "*.ot", "schnell_grid.jpeg"],
                    max_workers=1,
                )
            except Exception as e2:
                if "403" in str(e2) or "Forbidden" in str(e2):
                    raise PermissionError(_GATED_403_MSG) from e2
                raise
            logger.info("Flux Schnell: modello scaricato in cache -> '%s'", local_model_dir)

        # Carica pipeline dalla cache locale — nessuna chiamata al Hub, nessun 403.
        pipe = FluxPipeline.from_pretrained(
            local_model_dir,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )

        if torch.backends.mps.is_available():
            pipe = pipe.to("mps")
            logger.info("Flux Schnell: backend MPS (Apple Silicon Metal) attivo")
        elif torch.cuda.is_available():
            pipe = pipe.to("cuda")
            logger.info("Flux Schnell: backend CUDA attivo")
        else:
            logger.warning("Flux Schnell: nessuna GPU, uso CPU (lento)")

        pipe.enable_attention_slicing()
        _pipeline = pipe
        logger.info("Flux Schnell: pipeline pronta")
        return _pipeline

    except PermissionError:
        raise
    except ImportError as e:
        logger.error("Flux Schnell: dipendenze mancanti -> pip install -r requirements-flux.txt\n%s", e)
        raise
    except Exception as e:
        logger.error("Flux Schnell: errore caricamento pipeline: %s", e)
        raise


def _ensure_output_dir() -> Path:
    output_dir = Path(settings.image_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


async def generate_image_flux_schnell(prompt: str) -> dict:
    import asyncio

    logger.info("Flux Schnell: avvio generazione immagine")

    def _generate_sync():
        pipe = _get_pipeline()
        result = pipe(
            prompt=prompt,
            width=settings.image_width,
            height=settings.image_height,
            num_inference_steps=settings.flux_num_inference_steps,
            guidance_scale=settings.flux_guidance_scale,
            max_sequence_length=256,
        )
        return result.images[0]

    try:
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(None, _generate_sync)

        output_dir = _ensure_output_dir()
        filename = f"background_{uuid.uuid4().hex[:8]}.png"
        filepath = output_dir / filename
        image.save(str(filepath))
        logger.info("Flux Schnell: immagine salvata in '%s'", filepath)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        img_b64 = base64.b64encode(buffer.getvalue()).decode()

        return {
            "image_base64": img_b64,
            "image_path": str(filepath),
            "generation_status": "generated",
            "generation_model": MODEL_ID,
        }

    except PermissionError as e:
        logger.error("%s", e)
        return {"image_base64": None, "image_path": None, "generation_status": "error", "generation_model": MODEL_ID}
    except Exception as e:
        logger.error("Flux Schnell: errore generazione: %s", e)
        return {"image_base64": None, "image_path": None, "generation_status": "error", "generation_model": MODEL_ID}