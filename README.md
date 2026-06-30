# FullForce Assets Generator 4 Campaigns

FullForce Assets Generator 4 Campaigns is a FastAPI + LangGraph workflow for creating advertising background images from campaign briefs. It combines PDF brief extraction, copy generation, prompt generation for visual models, and image generation through multiple backends.

## What the repository does today

The app accepts a campaign brief, extracts structured data from a PDF, generates copy, and builds an image prompt for the Visual Expert agent. That prompt is then sent to the configured image backend.

### Main capabilities

- Extract structured briefing JSON from a PDF
- Generate headline, tagline, and copy text
- Generate an image prompt tailored to the briefing and custom palette
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

- `422` — text not extractable or invalid JSON
- `500` — Ollama error

---

### `POST /api/v1/campaign/generate`

Generates advertising copy and background image in parallel.

```bash
curl -X POST http://localhost:8000/api/v1/campaign/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product": "Regenerating Night Cream 50ml",
    "season": "Winter 2025",
    "audience": "Women 35-55, skin-conscious, premium lifestyle",
    "goal": "Increase brand awareness",
    "tone_of_voice": "Sophisticated and reassuring",
    "brand": "FullCosmetics — The Force of Beauty",
    "campaign_name": "Winter Ritual 2025",
    "key_messages": ["Deep skin regeneration", "Clinically tested"]
  }'
```

**Response:**
```json
{
  "briefing": { "product": "...", "season": "...", "..." },
  "copy": {
    "headline": "The ritual of the night.",
    "tagline": "Regenerated skin. Every morning.",
    "copy_text": "Complete advertising copy text..."
  },
  "visual": {
    "image_prompt": "Flat matte Champagne wall, soft diagonal light from the left...",
    "image_base64": "<base64 string>",
    "image_path": "output/images/background_a3f9c1e2.png",
    "generation_status": "generated",
    "generation_model": "pollinations/flux"
  },
  "status": "completed"
}
```

### `GET /api/v1/campaign/image/{filename}`

```bash
curl http://localhost:8000/api/v1/campaign/image/background_a3f9c1e2.png \
  --output background.png
```

### `generation_status` Values

| Status | Meaning |
|---|---|
| `generated` | PNG image created and available |
| `prompt_only` | Model doesn't support image gen, use `image_prompt` externally |
| `error` | Error during generation, check logs |

---

## MCP — Integration with External Clients

Compatible with Claude Desktop, Cursor, Continue and other MCP clients.

```bash
# List available tools
curl http://localhost:8000/mcp/tools

# Execute campaign generation
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "generate_campaign",
    "parameters": {
      "product": "Regenerating Night Cream 50ml",
      "season": "Winter 2025",
      "audience": "Women 35-55",
      "goal": "Increase brand awareness",
      "tone_of_voice": "Sophisticated and reassuring"
    }
  }'
```

---

## Backend Architecture

### FastAPI Application (`main.py`)

- Serves static HTML frontend from `frontend/`
- Mounts API routes from `app/api/routes.py`
- Mounts MCP server from `app/mcp/server.py`
- Configures CORS for external client access
- Runs on `APP_HOST:APP_PORT` (default: `0.0.0.0:8000`)

### Core Components

#### `app/core/config.py` — Configuration Management
- Reads environment variables from `.env` file
- Defines Pydantic `Settings` model
- Configures Ollama connection, image backend selection, and image output paths
- Validates backend choice (`pollinations`, `ollama`, `hf_inference`)

#### `app/core/schemas.py` — Data Models
- `BriefingInput`: required fields for campaign generation
- `BriefingJson`: structured output from PDF extraction
- `CopyResult`: copywriter agent output (headline, tagline, copy_text)
- `VisualResult`: visual expert output (image_prompt, image_path, base64, status)
- `CampaignOutput`: complete campaign response

### Agent Layer (`app/agents/`)

#### `coordinator.py` — LangGraph Orchestrator
- Builds a directed acyclic graph (DAG) with parallel fan-out
- Invokes `copywriter` and `visual_expert` nodes simultaneously
- Collects results via fan-in before returning
- Manages error handling and state threading

#### `copywriter.py` — Copy Generation Agent
- Uses `llama3.2` via Ollama
- Generates headline, tagline, and body copy
- Receives BriefingInput and produces CopyResult
- Respects `tone_of_voice` and `key_messages` from brief

#### `visual_expert.py` — Visual Prompt Generation Agent
- Uses `gemma4:e4b` via Ollama for FLUX prompt construction
- Analyzes product, season, audience, and tone
- Generates detailed image prompt following brand palette rules
- Outputs prompt to be passed to `image_generator`

#### `image_generator.py` — Backend Router
- Routes to selected backend (`IMAGE_BACKEND` env var)
- Applies `FLUX_NEGATIVE_PREFIX` to all prompts
- Returns image path and base64-encoded PNG
- Supports graceful fallback to `prompt_only` mode

#### `pollinations_generator.py` — Pollinations.ai Backend
- Calls Pollinations.ai HTTP API (GET request)
- Supports `flux`, `flux-realism`, `flux-anime`, `turbo` models
- Free, no API key required, no download overhead
- Default and recommended backend

#### `hf_inference_generator.py` — HuggingFace Inference API
- Calls HuggingFace Inference API (requires `HF_TOKEN`)
- Supports FLUX.1-schnell by default
- Requires HuggingFace account and available credits

#### `brief_extractor.py` — PDF Brief Extraction
- Uses `pymupdf` to extract text from PDF files
- Passes text to `llama3.2` for structured JSON extraction
- Returns validated `BriefingJson` output

#### `state.py` — LangGraph State Definition
- `CampaignState`: TypedDict containing intermediate results
- Threads briefing, copy, and visual data through the graph

### API Layer (`app/api/routes.py`)

- `POST /api/v1/campaign/brief_insights_extraction` — PDF → BriefingJson
- `POST /api/v1/campaign/generate` — BriefingInput → CampaignOutput
- `POST /api/v1/campaign/copy` — BriefingInput → CopyResult (copy only)
- `POST /api/v1/campaign/background` — BriefingInput → VisualResult (visual only)
- `GET /api/v1/campaign/image/{filename}` — retrieve saved image
- `GET /api/v1/health` — service health check

---

## Frontend Architecture (`frontend/index.html`)

### UI Components

- **Input Form**: fields for product, season, audience, goal, tone_of_voice, brand, campaign_name, key_messages
- **Progress Bar**: visible during campaign generation
- **Copy Output Panel**: displays headline, tagline, and copy text
- **Image Preview**: shows generated background image centered in the viewport
- **Image Details**: displays generation model and status
- **Download Button**: allows saving generated image locally
- **Error Display**: shows error messages if generation fails

### Frontend Flow

1. User fills campaign briefing form
2. Clicks "Generate Campaign"
3. Frontend makes `POST /api/v1/campaign/generate` request
4. Progress bar shows generation status
5. Once complete:
   - Copy results displayed in left panel
   - Image preview displayed in right panel (centered)
   - User can download image or regenerate

### Styling

- Clean, minimalist design
- Responsive layout (desktop-first)
- Uses CSS Grid for two-column layout (form/controls left, output right)
- Brand colors from palette used for accents
- Smooth transitions and loading states

---

## MCP Server Integration (`app/mcp/`)

The Model Context Protocol (MCP) server exposes backend services as callable tools for external clients (Claude Desktop, Cursor, Continue, etc.) and Workfront automation workflows.

### MCP HTTP Endpoints

#### `GET /mcp/tools`

Returns list of available tools that can be invoked.

```bash
curl http://localhost:8000/mcp/tools | jq
```

**Response:**
```json
[
  {
    "name": "extract_brief",
    "description": "Extract brief information from user input",
    "inputSchema": {
      "type": "object",
      "properties": {
        "user_input": { "type": "string" }
      },
      "required": ["user_input"]
    }
  },
  {
    "name": "generate_campaign",
    "description": "Generate advertising copy and background image",
    "inputSchema": {
      "type": "object",
      "properties": {
        "product": { "type": "string" },
        "season": { "type": "string" },
        "audience": { "type": "string" },
        "goal": { "type": "string" },
        "tone_of_voice": { "type": "string" },
        "brand": { "type": "string" },
        "campaign_name": { "type": "string" },
        "key_messages": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["product", "season", "audience", "goal", "tone_of_voice", "brand"]
    }
  },
  {
    "name": "generate_copy",
    "description": "Generate advertising copy only (headline, tagline, text)",
    "inputSchema": { "..." }
  },
  {
    "name": "generate_background",
    "description": "Generate background image only with FLUX prompt",
    "inputSchema": { "..." }
  },
  {
    "name": "get_image",
    "description": "Retrieve a previously generated image by filename",
    "inputSchema": {
      "type": "object",
      "properties": {
        "filename": { "type": "string" }
      },
      "required": ["filename"]
    }
  },
  {
    "name": "health",
    "description": "Check service health and connectivity",
    "inputSchema": { "type": "object", "properties": {} }
  }
]
```

#### `POST /mcp/call`

Executes an MCP tool with the given parameters.

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

**Response:**
```json
{
  "tool_name": "generate_campaign",
  "status": "success",
  "result": {
    "briefing": { "..." },
    "copy": { "headline": "...", "tagline": "...", "copy_text": "..." },
    "visual": { "image_prompt": "...", "image_path": "...", "image_base64": "...", "generation_status": "generated" },
    "status": "completed"
  }
}
```

### MCP Tool Definitions (`app/mcp/tools.py`)

- Defines tool schemas for each backend service
- Maps tool names to handler functions
- Validates input parameters against schemas
- Handles errors and returns structured responses

### MCP Server Implementation (`app/mcp/server.py`)

- Implements `GET /mcp/tools` endpoint to list available tools
- Implements `POST /mcp/call` endpoint to execute tools
- Dispatches tool execution to `tools.py` handlers
- Routes to FastAPI endpoints or direct agent invocation

### Workfront Integration Example

You can invoke the MCP server from Workfront automation:

```json
{
  "endpoint": "https://your-app.com/mcp/call",
  "method": "POST",
  "body": {
    "tool_name": "generate_campaign",
    "parameters": {
      "product": "{product_name}",
      "season": "{current_season}",
      "audience": "{target_audience}",
      "goal": "{campaign_goal}",
      "tone_of_voice": "Professional",
      "brand": "FullCosmetics — The Force of Beauty"
    }
  }
}
```

---

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_LLM_MODEL` | `llama3.2` | LLM for copywriter and brief extractor |
| `OLLAMA_VISION_MODEL` | `gemma4:e4b` | LLM for visual prompt generation |
| `OLLAMA_IMAGE_MODEL` | `x/z-image-turbo` | Image model (only `IMAGE_BACKEND=ollama`) |
| `IMAGE_BACKEND` | `pollinations` | Backend: `pollinations` \| `ollama` \| `hf_inference` |
| `POLLINATIONS_MODEL` | `flux` | Pollinations model: `flux` \| `flux-realism` \| `flux-anime` \| `turbo` |
| `HF_TOKEN` | — | HuggingFace token (only `hf_inference`) |
| `HF_INFERENCE_MODEL` | `black-forest-labs/FLUX.1-schnell` | HF Inference API model |
| `IMAGE_OUTPUT_DIR` | `output/images` | Image save directory |
| `IMAGE_WIDTH` | `1024` | Image width in pixels |
| `IMAGE_HEIGHT` | `768` | Image height in pixels |
| `APP_HOST` | `0.0.0.0` | FastAPI host |
| `APP_PORT` | `8000` | FastAPI port |
| `LOG_LEVEL` | `info` | Log level: `debug` \| `info` \| `warning` \| `error` |

---

## Recommended Ollama Models (Mac M4)

| Role | Model | RAM | Command |
|---|---|---|---|
| Copywriter + Brief Extractor | `llama3.2` | ~3 GB | `ollama pull llama3.2` |
| Visual Expert | `gemma4:e4b` | ~5 GB | `ollama pull gemma4:e4b` |
| Image (optional) | `x/z-image-turbo` | ~3 GB | `ollama pull x/z-image-turbo` |

With `pollinations` backend, only the two LLMs are needed: ~8 GB total, compatible with Mac M4 16 GB.

---

## Testing

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

> Requires active Ollama with `llama3.2` and `gemma4:e4b`.
> To test `brief_insights_extraction` use `tests/brief_test_fullcosmetics.pdf`.

---

## Human Review Validation Workflow

1. **Extract Brief** → `POST /api/v1/campaign/brief_insights_extraction` with PDF → structured JSON
2. **Generate Campaign** → `POST /api/v1/campaign/generate` with JSON → copy + background
3. **Validate Copy** → review headline, tagline, copy_text
4. **Validate Visual** → open PNG in `output/images/` — must be empty matte wall with diagonal light, zero objects
5. **If image unsatisfactory** → change `POLLINATIONS_MODEL` (try `flux-realism`) and retry
6. **Approve and deploy**
