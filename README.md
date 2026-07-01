# FullForce Assets Generator 4 Campaigns

FullForce Assets Generator 4 Campaigns is a complete FastAPI + LangGraph application for turning campaign briefs into advertising copy and background visuals. It supports PDF brief extraction, copy generation, visual prompt generation, image generation, a browser-based frontend, and an MCP endpoint layer for external automation and AI tools.

## What this project does

The system takes a campaign brief, extracts structured information from a PDF, generates marketing copy, creates a visual prompt for the Visual Expert, and sends that prompt to an image backend to produce a background image. The result can then be reviewed in a simple UI or consumed via REST or MCP endpoints.

### Core capabilities

- Extract structured campaign JSON from a PDF briefing
- Generate top_label, headline, subheadline, and trust_badges copy
- Build a prompt for FLUX-style image generation from the briefing and palette
- Generate background images through Pollinations, Hugging Face Inference, Ollama, or OneDrive-based selection
- Provide a browser UI for form input, palette editing, image generation, and prompt inspection
- Expose REST endpoints and MCP tools for automation and external clients

## Architecture at a glance

The repository is organized around a FastAPI app, a LangGraph agent workflow, and several backend modules.

- API layer: [app/api/routes.py](app/api/routes.py)
- Agent orchestration: [app/agents/coordinator.py](app/agents/coordinator.py)
- Brief extraction: [app/agents/brief_extractor.py](app/agents/brief_extractor.py)
- Copy generation: [app/agents/copywriter.py](app/agents/copywriter.py)
- Visual prompt generation: [app/agents/visual_expert.py](app/agents/visual_expert.py)
- Image backend router: [app/agents/image_generator.py](app/agents/image_generator.py)
- Frontend UI: [frontend/index.html](frontend/index.html)
- MCP server: [app/mcp/server.py](app/mcp/server.py)

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

The application reads configuration from a local `.env` file using [app/core/config.py](app/core/config.py).

Useful environment variables include:

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

Example:

```bash
cp .env.example .env
```

## Running the app locally

Start the server with:

```bash
python main.py
```

Open:

- <http://localhost:8000/>
- <http://localhost:8000/docs>

## Backend workflow

### 1. PDF briefing extraction

The endpoint `POST /api/v1/campaign/brief_insights_extraction` accepts a PDF and returns a structured `BriefingJson` object.

Example:

```bash
curl -X POST http://localhost:8000/api/v1/campaign/brief_insights_extraction \
  -F "file=@briefing.pdf"
```

### 2. Campaign generation

The endpoint `POST /api/v1/campaign/generate_copy_and_background` accepts a structured briefing and runs the workflow.

Example payload:

```json
{
  "product": "Regenerating Night Cream 50ml",
  "season": "Winter 2025",
  "audience": "Women 35-55, skin-conscious, premium lifestyle",
  "goal": "Increase brand awareness",
  "tone_of_voice": "Sophisticated and reassuring",
  "brand": "FullCosmetics — The Force of Beauty",
  "campaign_name": "Winter Ritual 2025",
  "key_messages": [
    "Deep skin regeneration while you sleep",
    "Clinically tested formula"
  ]
}
```

### 3. Copy and visual outputs

The campaign workflow returns:

- copy: top_label, headline, subheadline, and trust_badges text
- visual: image prompt, image path, base64 image, generation status, and generation model

## REST API reference

### Brief extraction

- `POST /api/v1/campaign/brief_insights_extraction`
- Uploads a PDF and returns structured briefing JSON

### Generate full campaign

- `POST /api/v1/campaign/generate_copy_and_background`
- Returns both copy and visual output

### Generate copy only

- `POST /api/v1/campaign/generate_copy`

### Generate background only

- `POST /api/v1/campaign/generate_background`

### Retrieve generated image

- `GET /api/v1/campaign/image/{filename}`

### Health check

- `GET /api/v1/health`

## Frontend

The frontend is a single-page app in [frontend/index.html](frontend/index.html). It provides:

- a campaign briefing form
- PDF upload and extraction flow
- palette editing for user-selected brand colors
- copy and background generation actions
- a prompt viewer for the generated FLUX prompt
- image preview and download controls

The page uses the REST API to trigger copy generation and background generation separately, and it shows the returned results in the UI.

## MCP server

The MCP server exposes the core capabilities as callable tools for external automation clients such as Claude Desktop, Cursor, Continue, or integration workflows.

### Available MCP endpoints

- `GET /mcp/tools` — list all available tools
- `POST /mcp/call` — execute a tool by name

### Available MCP tools

The MCP layer is defined in [app/mcp/tools.py](app/mcp/tools.py) and implemented in [app/mcp/server.py](app/mcp/server.py).

Available tools include:

- `extract_brief_from_pdf`
- `generate_campaign`
- `generate_copy`
- `generate_background`
- `get_campaign_image`
- `health_check`
- `get_ready_briefings` (mock Workfront-style integration)

### Example: list tools

```bash
curl http://localhost:8000/mcp/tools
```

### Example: run a campaign via MCP

```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "generate_campaign",
    "parameters": {
      "product": "Regenerating Night Cream 50ml",
      "season": "Winter 2025",
      "audience": "Women 35-55",
      "goal": "Increase brand awareness",
      "tone_of_voice": "Sophisticated and reassuring",
      "brand": "FullCosmetics — The Force of Beauty"
    }
  }'
```

## Core modules

### FastAPI app entrypoint

- [main.py](main.py) mounts the REST API, MCP router, and the frontend static files.

### Configuration details

- [app/core/config.py](app/core/config.py) defines the settings model and reads environment variables from `.env`.

### Schemas

- [app/core/schemas.py](app/core/schemas.py) contains the request and response models used by the API and MCP layer.

### Agent layer

#### Coordinator

- [app/agents/coordinator.py](app/agents/coordinator.py) orchestrates the workflow with LangGraph and fan-out/fan-in logic.

#### Copywriter

- [app/agents/copywriter.py](app/agents/copywriter.py) generates the copy assets from the briefing.

#### Visual Expert

- [app/agents/visual_expert.py](app/agents/visual_expert.py) creates the prompt that guides image generation based on the briefing and selected palette.

#### Brief extractor

- [app/agents/brief_extractor.py](app/agents/brief_extractor.py) extracts structured JSON from a PDF briefing.

#### Image generator router

- [app/agents/image_generator.py](app/agents/image_generator.py) routes the prompt to the configured image backend.

### Image backends

The image router supports:

- `pollinations` — default backend
- `ollama`
- `hf_inference`
- `onedrive`

The Pollinations backend is the default and requires no API key.

## Testing

Run the test suite with:

```bash
pytest -q
```

The project includes tests for the campaign flow and MCP server layer in [tests](tests).

## Notes

- The app is designed for human review and iterative refinement.
- The generated image is stored under the configured output directory, by default [output/images](output/images).
- The Visual Expert prompt and image router are intentionally tuned to reduce common object-generation issues and keep generated backgrounds minimal and pack-shot ready.

