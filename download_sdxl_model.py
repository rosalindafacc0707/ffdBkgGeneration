"""
Script one-shot per scaricare SDXL Base 1.0 nella cache locale.
Eseguire UNA VOLTA prima di avviare l'app con IMAGE_BACKEND=sdxl:

    python download_sdxl_model.py

Dopo il completamento (~6.5 GB), l'app caricherà il modello dalla cache
senza più contattare HuggingFace. Nessun token necessario.
"""
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"


def main():
    try:
        from diffusers import StableDiffusionXLPipeline
        import torch
    except ImportError:
        logger.error(
            "Dipendenze mancanti. Esegui:\n"
            "  pip install -r requirements-flux.txt"
        )
        sys.exit(1)

    logger.info("Download SDXL Base 1.0 (~6.5 GB)... questo richiede qualche minuto.")
    logger.info("Il download è resumabile: se si interrompe, riesegui questo script.")

    try:
        StableDiffusionXLPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
        )
        logger.info("Download completato ✓")
        logger.info(
            "Imposta nel .env:\n"
            "  IMAGE_BACKEND=sdxl\n"
            "Poi avvia l'app con: python main.py"
        )
    except KeyboardInterrupt:
        logger.info(
            "\nDownload interrotto. I file già scaricati sono in cache: "
            "riesegui lo script per riprendere."
        )
        sys.exit(0)
    except Exception as e:
        logger.error("Errore durante il download: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
