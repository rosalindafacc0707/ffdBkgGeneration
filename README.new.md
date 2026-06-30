# FullForce Assets Generator 4 Campaigns

FullForce Assets Generator 4 Campaigns is a FastAPI + LangGraph workflow for producing advertising background images from campaign briefs. It combines:

- PDF brief extraction
- copy generation
- visual prompt generation for FLUX-style image models
- image generation through multiple backends
- a lightweight frontend for manual review and generation

## What the repository does today

The app accepts a campaign brief, extracts structured data from a PDF, generates copy, and creates a background image prompt for the Visual Expert agent. The image prompt is then sent to the configured image backend.

### Main capabilities

- Extract structured briefing JSON from a PDF
- Generate headline, tagline, and copy text
- Generate an image prompt tailored to the briefing and selected palette
- Generate background images via Pollinations, Hugging Face Inference, Ollama, or OneDrive-based selection
- Serve a browser UI from the frontend folder
- Expose REST and MCP-style routes for integration

## Architecture

- API layer: [app/api/routes.py](app/api/routes.py)
- Agent orchestration: [app/agents/coordinator.py](app/agents/coordinator.py)
- Brief extraction: [app/agents/brief_extractor.py](app/agents/brief_extractor.py)
- Copy generation: [app/agents/copywriter.py](app/agents/copywriter.py)
- Visual prompt generation: [app/agents/visual_expert.py](app/agents/visual_expert.py)
- Image backend router: [app/agents/image_generator.py](app/agents/image_generator.py)
- Frontend UI: [frontend/index.html](frontend/index.html)

## Project structure

```text
app/
  agents/
    brief_extractor.py
    coordinator.py
    copywriter.py
    hf_inference_generator.py
    image_generator.py
    onedrive_selector.py
    pollinations_generator.py
    state.py
    visual_expert.py
  api/
    routes.py
  core/
    config.py
    schemas.py
  mcp/
    server.py
    tools.py
    workfront_mock.py
frontend/
  index.html
main.py
requirements.txt
tests/
```

## Requirements

Python 3.11+ is recommended.

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

The app reads environment variables from a local `.env` file via [app/core/config.py](app/core/config.py).

Common settings include:

- `OLLAMA_BASE_URL`
- `OLLAMA_LLM_MODEL`
- `OLLAMA_VISION_MODEL`
- `IMAGE_BACKEND` (`pollinations`, `ollama`, `hf_inference`, `onedrive`)
- `POLLINATIONS_MODEL`
- `HF_TOKEN`
- `HF_INFERENCE_MODEL`
- `IMAGE_OUTPUT_DIR`

Example:

```bash
cp .env.example .env
```

## Run locally

```bash
python main.py
```

Then open:

- http://localhost:8000/
- http://localhost:8000/docs

## API endpoints

### Brief extraction

`POST /api/v1/campaign/brief_insights_extraction`

Uploads a PDF and returns a structured briefing JSON.

### Generate full campaign

`POST /api/v1/campaign/generate_copy_and_background`

Receives a structured briefing and returns both copy and visual output.

### Generate copy only

`POST /api/v1/campaign/generate_copy`

### Generate background only

`POST /api/v1/campaign/generate_background`

### Health check

`GET /api/v1/health`

## Frontend

The frontend is a single-page UI in [frontend/index.html](frontend/index.html). It lets users:

- upload a PDF briefing
- edit the generated briefing fields
- choose and edit a brand palette
- generate copy and background
- view the resulting FLUX prompt

## Image generation backends

The image generation flow is routed by [app/agents/image_generator.py](app/agents/image_generator.py).

Supported backends:

- `pollinations` — default backend
- `ollama`
- `hf_inference`
- `onedrive`

## Testing

Run tests with:

```bash
pytest -q
```

The repository includes tests for the campaign flow and MCP server integration in [tests](tests).
