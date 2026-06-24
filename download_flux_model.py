"""
Script one-shot per scaricare FLUX.1-schnell nella cache locale.
Eseguire UNA VOLTA prima di avviare l'app:

    python download_flux_model.py

Dopo il completamento, l'app caricherà il modello dalla cache senza
più contattare HuggingFace.
"""
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_ID = "black-forest-labs/FLUX.1-schnell"


def main():
    # Legge HF_TOKEN dal .env se presente, altrimenti dall'ambiente
    token = os.environ.get("HF_TOKEN")
    if not token:
        try:
            from dotenv import dotenv_values
            env = dotenv_values(".env")
            token = env.get("HF_TOKEN")
        except ImportError:
            pass

    if not token:
        logger.error(
            "HF_TOKEN non trovato. Impostalo nel file .env oppure come variabile d'ambiente:\n"
            "  export HF_TOKEN=hf_tuotoken"
        )
        sys.exit(1)

    os.environ["HF_TOKEN"] = token
    os.environ["HUGGING_FACE_HUB_TOKEN"] = token

    try:
        from huggingface_hub import login, snapshot_download, hf_hub_download
    except ImportError:
        logger.error("huggingface_hub non installato. Esegui: pip install -r requirements-flux.txt")
        sys.exit(1)

    # Login esplicito
    login(token=token, add_to_git_credential=False)
    logger.info("Login HuggingFace OK ✓")

    # Verifica accesso con file piccolo prima di avviare il download pesante
    logger.info("Verifica accesso al modello gated...")
    try:
        hf_hub_download(repo_id=MODEL_ID, filename="model_index.json", token=token)
        logger.info("Accesso ai file verificato ✓")
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            logger.error(
                "\n" + "="*60 + "\n"
                "ACCESSO NEGATO (403).\n"
                "Vai su https://huggingface.co/black-forest-labs/FLUX.1-schnell\n"
                "e clicca 'Agree and access repository' con l'account del tuo token.\n"
                + "="*60
            )
        else:
            logger.error("Errore verifica accesso: %s", e)
        sys.exit(1)

    # Download completo con retry automatico e resume
    logger.info(
        "Avvio download FLUX.1-schnell (~17 GB, solo pesi fp8 / ~57 GB versione completa).\n"
        "Il download è resumabile: se si interrompe, riesegui questo script."
    )

    try:
        local_dir = snapshot_download(
            repo_id=MODEL_ID,
            token=token,
            ignore_patterns=[
                "*.msgpack",
                "*.h5",
                "flax_model*",
                "*.ot",
                "schnell_grid.jpeg",  # immagine di esempio, non necessaria
            ],
            # max_workers=1 evita il crash "Background writer channel closed"
            # che avviene quando più thread scrivono file grandi contemporaneamente
            max_workers=1,
        )
        logger.info("Download completato ✓  Cache locale: %s", local_dir)
        logger.info("Puoi ora avviare l'app con: python main.py")

    except KeyboardInterrupt:
        logger.info(
            "\nDownload interrotto dall'utente.\n"
            "I file già scaricati sono in cache: riesegui lo script per riprendere."
        )
        sys.exit(0)
    except Exception as e:
        logger.error("Errore durante il download: %s", e)
        logger.info(
            "I file parzialmente scaricati sono in cache.\n"
            "Riesegui questo script per riprendere il download."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
