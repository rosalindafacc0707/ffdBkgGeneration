from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal, Optional


class Settings(BaseSettings):
    # Ollama — LLM
    ollama_base_url: str = Field("http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_llm_model: str = Field("llama3.2", env="OLLAMA_LLM_MODEL")
    ollama_vision_model: str = Field("gemma4:e4b", env="OLLAMA_VISION_MODEL")
    ollama_image_model: str = Field("x/z-image-turbo", env="OLLAMA_IMAGE_MODEL")

    # Image backend:
    #   "ollama"         → Ollama locale, nessun token
    #   "pollinations"   → Pollinations.ai, gratuito, nessun token  ← DEFAULT
    #   "hf_inference"   → HuggingFace Inference API (richiede crediti)
    image_backend: Literal["ollama", "pollinations", "hf_inference"] = Field(
        "pollinations", env="IMAGE_BACKEND"
    )

    # Pollinations.ai — nessuna API key richiesta
    # Modelli: flux (default), flux-realism, flux-anime, turbo
    pollinations_model: str = Field("flux", env="POLLINATIONS_MODEL")

    # HuggingFace — per hf_inference
    hf_token: Optional[str] = Field(None, env="HF_TOKEN")
    hf_inference_model: str = Field(
        "black-forest-labs/FLUX.1-schnell", env="HF_INFERENCE_MODEL"
    )

    # Image output
    image_output_dir: str = Field("output/images", env="IMAGE_OUTPUT_DIR")
    image_width: int = Field(1024, env="IMAGE_WIDTH")
    image_height: int = Field(768, env="IMAGE_HEIGHT")

    # App
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    log_level: str = Field("info", env="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_file_override": True,
    }


settings = Settings()
