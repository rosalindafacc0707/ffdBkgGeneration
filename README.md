# FullForce Ad Generator 🎯

Agentic system for automatic generation of advertising backgrounds for dermatological and cosmetic product campaigns.
Built on **FastAPI** + **LangGraph** + **Ollama** (100% local LLM) + **Pollinations.ai** (image generation, free, no subscription).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT                                        │
│  POST /campaign/brief_insights_extraction  →  PDF Upload            │
│  POST /campaign/generate                   →  JSON Briefing         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  COORDINATOR    │  (LangGraph — parallel fan-out)
                  └────────┬────────┘
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
   ┌─────────────────┐     ┌───────────────────────────────────────┐
   │   COPYWRITER    │     │            VISUAL EXPERT              │
   │  (llama3.2)     │     │  1. gemma4:e4b → FLUX prompt          │
   │                 │     │  2. image_generator                   │
   │  → headline     │     │     → FLUX_NEGATIVE_PREFIX applied    │
   │  → tagline      │     │     → pollinations_generator          │
   │  → copy_text    │     │  → image_path + base64                │
   └────────┬────────┘     └──────────────────┬────────────────────┘
            │                                 │
            └─────────────┬───────────────────┘
                          │ fan-in
                          ▼
           Output for Human Review
           • copy:   headline + tagline + copy_text
           • visual: image_prompt + image_path + base64
```

---

## Complete workflow with brief extraction

```
PDF Briefing
    │
    ▼
POST /campaign/brief_insights_extraction
    │  brief_extractor.py
    │  • pymupdf → extracts PDF text
    │  • llama3.2 → extracts structured JSON
    │
    ▼
BriefingJson
{
  "product", "season", "audience", "goal",
  "tone_of_voice", "brand", "campaign_name",
  "key_messages", "raw_extraction"
}
    │
    ▼  (uses required fields as input to /campaign/generate)
POST /campaign/generate
    │
    ▼
CampaignOutput
{
  "copy":   { headline, tagline, copy_text },
  "visual": { image_prompt, image_path, image_base64, ... }
}
```

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running
- Ollama models to download:

```bash
ollama pull llama3.2       # LLM copywriter + brief extractor
ollama pull gemma4:e4b     # LLM visual expert (FLUX prompt generation)
```

> For image generation the default backend is **Pollinations.ai** — cloud, free, no download required.

---

## Setup

```bash
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Base dependencies (includes pymupdf for PDF reading)
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
# Verify IMAGE_BACKEND=pollinations in .env

# 4. Start
python main.py
```

App: **http://localhost:8000** — Swagger UI: **http://localhost:8000/docs**

---

## Backend Image Generation

Selectable via `IMAGE_BACKEND` in `.env`. Default: `pollinations`.

### `pollinations` — default ✅

Calls [Pollinations.ai](https://pollinations.ai) via HTTP GET. Free, no API key, no download, no monthly rate limit.

```env
IMAGE_BACKEND=pollinations
POLLINATIONS_MODEL=flux        # flux | flux-realism | flux-anime | turbo
```

| Model | Style | Speed |
|---|---|---|
| `flux` | High quality | ~15-25 sec |
| `flux-realism` | Photorealistic | ~15-25 sec |
| `flux-anime` | Illustrative style | ~15-25 sec |
| `turbo` | Fast, lower quality | ~5-10 sec |

### Other backends

| Backend | Requirements | Notes |
|---|---|---|
| `ollama` | Image model installed locally | `OLLAMA_IMAGE_MODEL=x/z-image-turbo` |
| `hf_inference` | HF_TOKEN + HF credits | Free plan exhaustible |

---

## FLUX Negative Prefix — anti-hallucination for objects

FLUX tends to generate podiums and products in skincare scenes due to training data.
`image_generator.py` automatically prepends a negative prefix to all FLUX prompts:

```python
FLUX_NEGATIVE_PREFIX = (
    "EMPTY WALL ONLY. "
    "Absolutely no podium, no pedestal, no platform, no riser, no cylinder, no disc, "
    "no circular base, no geometric shape, no 3D object, no product, no cosmetic jar, "
    "no bottle, no tube, no container, no prop, no plant, no flower, no leaf, "
    "no shelf, no table, no furniture, no floor object, no shadow of any object, "
    "no hands, no people, no text, no logo, no pattern, no tile, no architectural detail. "
    "The frame contains ONLY a flat matte wall with light and shadow gradients. "
    "Zero objects. Zero props. Zero geometry. Pure empty background. "
)
```

Automatically applied to `pollinations` and `hf_inference`. Should not be included in Gemma prompt.

---

## Mandatory Brand Palette

The `visual_expert.py` uses exclusively these colors:

| Name | Hex | RGB |
|---|---|---|
| Blush | `#F9EDEF` | 249, 237, 239 |
| Champagne | `#E5C8B6` | 229, 200, 182 |
| Cognac | `#C3955A` | 195, 149, 90 |
| Amber | `#BA6A37` | 186, 106, 55 |
| Emerald | `#1C3934` | 28, 57, 52 |
| Noir | `#131315` | 19, 19, 21 |
| Espresso | `#241515` | 36, 21, 21 |
| Cappuccino | `#EBEAE0` | 235, 234, 224 |
| Cream | `#F3F2EB` | 243, 242, 235 |
| Flat White | `#F9F9F9` | 249, 249, 249 |

---

## Repository Structure

```
ffdBkgGeneration/
├── .env.example
├── .gitignore
├── requirements.txt                    ← base dependencies (includes pymupdf)
├── requirements-flux.txt               ← optional FLUX dependencies
├── main.py                             ← FastAPI application entry point
├── README.md
├── Dockerfile                          ← container image configuration
├── app/
│   ├── core/
│   │   ├── config.py                   ← Pydantic settings (reads .env)
│   │   └── schemas.py                  ← BriefingInput, BriefingJson,
│   │                                      CampaignOutput, VisualResult, CopyResult
│   ├── agents/
│   │   ├── state.py                    ← CampaignState TypedDict for LangGraph
│   │   ├── coordinator.py              ← LangGraph graph with parallel fan-out
│   │   ├── copywriter.py               ← copywriter agent → headline/tagline/copy
│   │   ├── visual_expert.py            ← visual agent → FLUX prompt via gemma4:e4b
│   │   ├── brief_extractor.py          ← extracts structured JSON from PDF via llama3.2
│   │   ├── image_generator.py          ← backend router + FLUX_NEGATIVE_PREFIX
│   │   ├── pollinations_generator.py   ← Pollinations.ai backend (default)
│   │   ├── hf_inference_generator.py   ← HuggingFace Inference API backend
│   │   └── flux_schnell_generator.py   ← deprecated FLUX Schnell backend
│   ├── api/
│   │   └── routes.py                   ← all FastAPI HTTP endpoints
│   └── mcp/
│       ├── tools.py                    ← MCP tool definitions and dispatch
│       ├── server.py                   ← MCP HTTP interface (GET /mcp/tools, POST /mcp/call)
│       └── __init__.py
├── frontend/
│   └── index.html                      ← static HTML UI for campaign generation
├── output/
│   └── images/                         ← generated images (gitignored)
└── tests/
    ├── __init__.py
    ├── test_campaign.py                ← campaign generation tests
    ├── test_mcp_server.py              ← MCP integration regression tests
    └── brief_test_fullcosmetics.pdf         ← example PDF for brief extraction testing
```

---

## API

### `POST /campaign/brief_insights_extraction`

Estrae JSON strutturato da un file PDF di briefing.

```bash
curl -X POST http://localhost:8000/api/v1/campaign/brief_insights_extraction \
  -F "file=@brief_campagna.pdf"
```

**Response:**
```json
{
  "product": "Regenerating Night Cream 50ml",
  "season": "Winter 2025",
  "audience": "Women 35-55, skin-conscious, premium lifestyle",
  "goal": "Increase brand awareness in the premium skincare segment",
  "tone_of_voice": "Sophisticated, reassuring, slightly clinical",
  "brand": "FullCosmetics — The Force of Beauty",
  "campaign_name": "Winter Ritual 2025",
  "key_messages": [
    "Deep skin regeneration while you sleep",
    "Clinically tested formula, dermatologist approved",
    "Science-backed: hyaluronic acid + retinol complex"
  ],
  "raw_extraction": "--- Page 1 ---\nCAMPAIGN BRIEF..."
}
```

**Error codes:**
- `415` — unsupported file format (PDF only)
- `413` — file too large (max 10 MB)
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
