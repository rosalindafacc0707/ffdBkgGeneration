# FullForce Ad Generator

FullForce Ad Generator is a FastAPI-based campaign asset workflow that turns a campaign brief into polished marketing copy, a visual prompt, and a generated background image. It also includes a lightweight browser UI, an MCP interface for automation, and an assembly step that uploads the final image and DOCX copy to Azure Blob Storage.

## What this repository contains

This project combines:

- a FastAPI API for campaign generation and asset assembly
- a LangGraph-style orchestration layer for multi-agent copy and visual generation
- a browser-based frontend for manual review and interaction
- an MCP server for tool-based automation and external integrations
- Azure Blob Storage support for publishing final assets

The core flow is:

1. ingest a campaign brief (PDF or structured JSON)
2. extract structured briefing insights
3. generate copy and a visual prompt
4. produce a background image with an image backend
5. assemble the final content into a DOCX document and upload both assets to Azure Blob Storage

## Current capabilities

- parse PDF briefing files and extract structured campaign JSON
- generate campaign copy with fields such as top label, headline, subheadline, and trust badges
- build visual prompts for background-image generation
- route image generation through multiple backends:
  - Pollinations
  - Ollama
  - Hugging Face Inference
  - OneDrive-based image selection
- expose a simple frontend for generation and review
- provide REST endpoints for full campaign generation, copy-only generation, visual-only generation, and asset assembly
- expose an MCP layer for tool-based external integrations
- upload generated assets to Azure Blob Storage for downstream use

## Repository structure

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
  utils/
    azure_storage.py
frontend/
  index.html
input/
  briefings/
output/
  images/
tests/
  test_campaign.py
  test_mcp_server.py
  test_visual_expert.py
  test_azure_storage.py
main.py
requirements.txt
```

## Architecture overview

The application is organized around four main layers:

- API layer: [app/api/routes.py](app/api/routes.py)
  - exposes the REST endpoints used by the UI and external clients
- Agent layer: [app/agents](app/agents)
  - coordinates copy generation, visual prompt generation, and image generation
- Core layer: [app/core](app/core)
  - holds configuration, environment settings, and shared Pydantic schemas
- MCP layer: [app/mcp](app/mcp)
  - exposes the system as a tool-oriented interface for automation clients

Storage and delivery are handled by:

- [app/utils/azure_storage.py](app/utils/azure_storage.py)
  - creates an Azure Blob client and uploads bytes to the configured container
- [frontend/index.html](frontend/index.html)
  - provides a browser-based UI for working with generated assets

## Prerequisites

- Python 3.11 or newer
- access to an Azure Storage account (for the assembly upload step)
- optional: Ollama installed locally if you want to use the Ollama-based generation paths
- optional: a Hugging Face token if you want to use the Hugging Face inference backend

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you plan to use Azure Blob uploads, install the Azure dependency explicitly as well:

```bash
pip install azure-storage-blob
```

## Configuration

The app reads its settings from a local `.env` file using [app/core/config.py](app/core/config.py).

Typical environment variables include:

- `OLLAMA_BASE_URL`
- `OLLAMA_LLM_MODEL`
- `OLLAMA_VISION_MODEL`
- `OLLAMA_IMAGE_MODEL`
- `IMAGE_BACKEND` (`pollinations`, `ollama`, `hf_inference`, `onedrive`)
- `POLLINATIONS_MODEL`
- `HF_TOKEN`
- `HF_INFERENCE_MODEL`
- `IMAGE_OUTPUT_DIR`
- `IMAGE_WIDTH`
- `IMAGE_HEIGHT`
- `APP_HOST`
- `APP_PORT`
- `LOG_LEVEL`
- `AZURE_STORAGE_CONNECTION_STRING`
- `AZURE_STORAGE_CONTAINER_NAME`

Example `.env` values:

```bash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.2
IMAGE_BACKEND=pollinations
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
AZURE_STORAGE_CONTAINER_NAME=generatedfiles
```

## Running the application locally

Start the server with:

```bash
python main.py
```

Then open:

- http://localhost:8000/
- http://localhost:8000/docs

The FastAPI docs page exposes the available API routes and request/response models.

## Main workflows

### 1. Extract briefing insights from a PDF

Endpoint:

- `POST /api/v1/campaign/brief_insights_extraction`

This accepts a PDF file and returns a structured JSON object describing the campaign insights.

Example:

```bash
curl -X POST http://localhost:8000/api/v1/campaign/brief_insights_extraction \
  -F "file=@briefing.pdf"
```

### 2. Generate a full campaign

Endpoint:

- `POST /api/v1/campaign/generate_copy_and_background`

This runs the full workflow and returns both copy and a visual result.

Example request body:

```json
{
  "product": "Regenerating Night Cream 50ml",
  "season": "Winter 2025",
  "audience": "Women 35-55, skincare-conscious, premium lifestyle",
  "goal": "Increase brand awareness and drive consideration",
  "tone_of_voice": "Sophisticated, reassuring, premium",
  "brand": "FullCosmetics — The Force of Beauty"
}
```

### 3. Generate copy only

Endpoint:

- `POST /api/v1/campaign/generate_copy`

Useful when the visual asset should be produced separately or at a later step.

### 4. Generate the background image only

Endpoint:

- `POST /api/v1/campaign/generate_background`

Useful when you want to generate the image independently from the textual copy.

### 5. Assemble and upload final assets

Endpoint:

- `POST /api/v1/campaign/assemble_content`

This endpoint takes the current image payload and the assembled campaign copy and uploads the generated PNG and DOCX assets to Azure Blob Storage.

The response contains the uploaded asset URLs so the generated files can be consumed or shared immediately.

## REST API reference

### Campaign endpoints

- `POST /api/v1/campaign/brief_insights_extraction`
  - upload a PDF brief and receive structured JSON
- `POST /api/v1/campaign/generate_copy_and_background`
  - run the full campaign workflow
- `POST /api/v1/campaign/generate_copy`
  - generate only the copy output
- `POST /api/v1/campaign/generate_background`
  - generate only the visual output
- `POST /api/v1/campaign/assemble_content`
  - upload the final image and DOCX copy to Azure Blob Storage
- `GET /api/v1/campaign/image/{filename}`
  - retrieve a generated image from the local output directory
- `GET /api/v1/health`
  - service health check

## Frontend

The browser UI lives in [frontend/index.html](frontend/index.html). It provides:

- a campaign briefing form
- PDF upload and extraction flow
- copy and background generation actions
- prompt inspection for the generated visual prompt
- image preview and download support
- a simple path for assembling and publishing final assets

## MCP server

The MCP server exposes the core workflow as callable tools for automation clients and AI assistants.

### MCP endpoints

- `GET /mcp/tools`
  - list all available tools
- `POST /mcp/call`
  - execute a tool by name

### Available tools

The MCP layer is implemented in [app/mcp/server.py](app/mcp/server.py) and [app/mcp/tools.py](app/mcp/tools.py). It currently supports:

- `extract_brief_from_pdf`
- `generate_campaign`
- `generate_copy`
- `generate_background`
- `get_campaign_image`
- `health_check`
- `get_ready_briefings`

Example:

```bash
curl http://localhost:8000/mcp/tools
```

## Testing

The repository includes unit and integration-style tests for the campaign flow, MCP layer, and Azure storage helper.

Run the test suite with:

```bash
pytest -q
```

Relevant test files include:

- [tests/test_campaign.py](tests/test_campaign.py)
- [tests/test_mcp_server.py](tests/test_mcp_server.py)
- [tests/test_visual_expert.py](tests/test_visual_expert.py)
- [tests/test_azure_storage.py](tests/test_azure_storage.py)

## Notes

- The generated image output is stored under [output/images](output/images) by default.
- The assembly step uploads final assets to Azure Blob Storage, so the app does not depend on a local OneDrive folder for final publishing.
- The system is intended for iterative human review and refinement of campaign assets.

