# FullForce Ad Generator 🎯

Sistema agentico per la generazione automatica di background pubblicitari per campagne di prodotti dermatologici e cosmetici.
Basato su **FastAPI** + **LangGraph** + **Ollama** (LLM 100% locale) + **Pollinations.ai** (image generation, gratuito, nessuna subscription).

## Architettura

```
Input JSON Briefing
        │
        ▼
  ┌─────────────┐
  │ COORDINATOR │  (LangGraph — fan-out parallelo)
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────────────┐     ┌─────────────────────────────────────────────────────────┐
│  COPYWRITER  │     │                    VISUAL EXPERT                        │
│  (llama3.2)  │     │  1. gemma4:e4b  → genera prompt ottimizzato per FLUX    │
│              │     │  2. image_generator → applica FLUX_NEGATIVE_PREFIX      │
│              │     │  3. pollinations_generator → chiama Pollinations.ai API │
└──────┬───────┘     └─────────────────────────────┬───────────────────────────┘
       │                                           │
       └──────────────────┬────────────────────────┘
                          │ fan-in
                          ▼
         Output per Validazione Umana
         • copy:   headline + tagline + testo
         • visual: image_prompt + image_path + base64
```

## Prerequisiti

- Python 3.11+
- [Ollama](https://ollama.ai) installato e attivo
- Modelli Ollama da scaricare:

```bash
ollama pull llama3.2       # LLM copywriter
ollama pull gemma4:e4b     # LLM visual expert (costruzione prompt FLUX)
```

> **Nota**: per la generazione immagini il backend default è **Pollinations.ai** (cloud, gratuito, nessun download). Non è necessario scaricare alcun modello immagine locale.

## Setup

```bash
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Dipendenze base
pip install -r requirements.txt

# 3. Configurazione
cp .env.example .env
# Verifica che IMAGE_BACKEND=pollinations nel .env

# 4. Avvio
python main.py
```

App disponibile su: **http://localhost:8000**
Swagger UI: **http://localhost:8000/docs**

## Backend image generation

Il backend è selezionabile via `IMAGE_BACKEND` nel `.env`. Il default consigliato è `pollinations`.

### `pollinations` — default ✅

Chiama [Pollinations.ai](https://pollinations.ai) via API HTTP GET. Completamente gratuito, nessuna API key, nessun download, nessun limite mensile.

```env
IMAGE_BACKEND=pollinations
POLLINATIONS_MODEL=flux        # flux | flux-realism | flux-anime | turbo
```

| Modello | Stile | Velocità |
|---|---|---|
| `flux` | Qualità alta, generico | ~15-25 sec |
| `flux-realism` | Fotorealistico | ~15-25 sec |
| `flux-anime` | Stile illustrativo | ~15-25 sec |
| `turbo` | Veloce, qualità inferiore | ~5-10 sec |

### `ollama` — locale

Usa il modello immagine configurato in `OLLAMA_IMAGE_MODEL` tramite Ollama locale.

```env
IMAGE_BACKEND=ollama
OLLAMA_IMAGE_MODEL=x/z-image-turbo
```

### `hf_inference` — HuggingFace Inference API

Richiede `HF_TOKEN` valido e crediti HF disponibili (piano free esauribile).

```env
IMAGE_BACKEND=hf_inference
HF_TOKEN=hf_tuotoken
HF_INFERENCE_MODEL=black-forest-labs/FLUX.1-schnell
```

### `flux_schnell` — HuggingFace diffusers locale

Scarica e usa FLUX.1-schnell in locale (~16 GB). Richiede `requirements-flux.txt` e token HF Fine-grained con accesso ai repo gated.

```env
IMAGE_BACKEND=flux_schnell
HF_TOKEN=hf_tuotoken
```

```bash
pip install -r requirements-flux.txt
```

### `sdxl` — SDXL diffusers locale

Usa SDXL Base 1.0 in locale (~6.5 GB). Richiede `requirements-flux.txt`.

```env
IMAGE_BACKEND=sdxl
```

### Tabella comparativa backend

| | `pollinations` | `ollama` | `hf_inference` | `flux_schnell` | `sdxl` |
|---|---|---|---|---|---|
| Costo | Gratuito | Gratuito | Crediti HF | Gratuito | Gratuito |
| API key | Non necessaria | Non necessaria | HF token | HF Fine-grained | Non necessaria |
| Download modello | Nessuno | Sì (Ollama) | Nessuno | ~16 GB | ~6.5 GB |
| RAM locale | Nessuna | ~3-5 GB | Nessuna | ~16 GB | ~8 GB |
| Velocità | ~15-25 sec | Variabile | ~10-30 sec | ~20-40 sec | ~30-60 sec |
| Dipendenze extra | Nessuna | Nessuna | Nessuna | requirements-flux.txt | requirements-flux.txt |

## FLUX Negative Prefix — anti-allucinazione oggetti

FLUX tende a generare podium/prodotti cosmetici nelle scene di skincare per effetto del training data. Per contrastarlo, `image_generator.py` antepone automaticamente un **prefisso negativo** a tutti i prompt inviati a backend FLUX (`pollinations`, `hf_inference`, `flux_schnell`):

```
"EMPTY WALL ONLY. Absolutely no podium, no pedestal, no platform, no riser,
no cylinder, no disc, no circular base, no geometric shape, no 3D object,
no product, no cosmetic jar, no bottle..."
```

Questo prefisso è definito come costante `FLUX_NEGATIVE_PREFIX` in `app/agents/image_generator.py` ed è applicato automaticamente — non è necessario includerlo nel prompt di Gemma.

## Struttura della repository

```
fullforce_ad_generator/
├── .env.example                        ← template variabili d'ambiente
├── .gitignore
├── requirements.txt                    ← dipendenze base
├── requirements-flux.txt               ← dipendenze per backend flux_schnell / sdxl
├── main.py                             ← entry point FastAPI
├── README.md
├── app/
│   ├── core/
│   │   ├── config.py                   ← settings Pydantic (legge .env)
│   │   └── schemas.py                  ← modelli I/O (BriefingInput, CampaignOutput…)
│   ├── agents/
│   │   ├── state.py                    ← CampaignState TypedDict per LangGraph
│   │   ├── coordinator.py              ← grafo LangGraph fan-out parallelo
│   │   ├── copywriter.py               ← agente copywriter → JSON copy
│   │   ├── visual_expert.py            ← agente visual → prompt FLUX via gemma4:e4b
│   │   ├── image_generator.py          ← router backend + FLUX_NEGATIVE_PREFIX
│   │   ├── pollinations_generator.py   ← backend Pollinations.ai (default)
│   │   ├── hf_inference_generator.py   ← backend HuggingFace Inference API
│   │   ├── flux_schnell_generator.py   ← backend FLUX.1-schnell via diffusers
│   │   └── sdxl_generator.py           ← backend SDXL via diffusers
│   ├── api/
│   │   └── routes.py                   ← POST /api/v1/campaign/generate
│   │                                      GET  /api/v1/campaign/image/{filename}
│   └── mcp/
│       ├── tools.py                    ← definizioni tool MCP
│       └── server.py                   ← GET /mcp/tools  POST /mcp/call
├── output/
│   └── images/                         ← immagini generate (gitignored)
└── tests/
    └── test_campaign.py
```

## API — Generare una campagna

### Endpoint principale

```
POST /api/v1/campaign/generate
Content-Type: application/json
```

**Body di esempio:**

```json
{
  "product": "Hand Cream for Dry Hands",
  "season": "Inverno 2025",
  "audience": "Donne 30-50 anni attente alla cura della pelle",
  "best_house_environment": "Bagno minimalista, luce naturale"
}
```

**Esempio curl:**

```bash
curl -X POST http://localhost:8000/api/v1/campaign/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product": "Hand Cream for Dry Hands",
    "season": "Inverno 2025",
    "audience": "Donne 30-50 anni attente alla cura della pelle",
    "best_house_environment": "Bagno minimalista, luce naturale"
  }'
```

### Scaricare l'immagine generata

```
GET /api/v1/campaign/image/{filename}
```

```bash
curl http://localhost:8000/api/v1/campaign/image/background_a3f9c1e2.png \
  --output background.png
```

## Output di esempio

```json
{
  "briefing": {
    "product": "Hand Cream for Dry Hands",
    "season": "Inverno 2025",
    "audience": "Donne 30-50 anni attente alla cura della pelle",
    "best_house_environment": "Bagno minimalista, luce naturale"
  },
  "copy": {
    "headline": "Mani che parlano di te",
    "tagline": "Idratazione profonda. Ogni giorno.",
    "copy_text": "Testo pubblicitario completo di 2-3 frasi evocative..."
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

### Valori possibili di `generation_status`

| Status | Significato |
|---|---|
| `generated` | Immagine PNG creata, disponibile in `image_path` e `image_base64` |
| `prompt_only` | Il modello non supporta image generation, usa `image_prompt` esternamente |
| `error` | Errore durante la generazione, controlla i log |

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL server Ollama |
| `OLLAMA_LLM_MODEL` | `llama3.2` | Modello LLM per il copywriter |
| `OLLAMA_VISION_MODEL` | `gemma4:e4b` | Modello LLM per costruire il prompt visivo |
| `OLLAMA_IMAGE_MODEL` | `x/z-image-turbo` | Modello image generation (solo `IMAGE_BACKEND=ollama`) |
| `IMAGE_BACKEND` | `pollinations` | Backend: `pollinations` \| `ollama` \| `hf_inference` \| `flux_schnell` \| `sdxl` |
| `POLLINATIONS_MODEL` | `flux` | Modello Pollinations: `flux` \| `flux-realism` \| `flux-anime` \| `turbo` |
| `HF_TOKEN` | — | Token HuggingFace (solo `hf_inference` e `flux_schnell`) |
| `HF_INFERENCE_MODEL` | `black-forest-labs/FLUX.1-schnell` | Modello HF Inference API |
| `IMAGE_OUTPUT_DIR` | `output/images` | Cartella salvataggio immagini |
| `IMAGE_WIDTH` | `1024` | Larghezza immagine in pixel |
| `IMAGE_HEIGHT` | `768` | Altezza immagine in pixel |
| `FLUX_NUM_INFERENCE_STEPS` | `4` | Step di inferenza (solo `flux_schnell`) |
| `FLUX_GUIDANCE_SCALE` | `0.0` | Guidance scale (solo `flux_schnell`) |
| `APP_HOST` | `0.0.0.0` | Host FastAPI |
| `APP_PORT` | `8000` | Porta FastAPI |
| `LOG_LEVEL` | `info` | Livello log: `debug` \| `info` \| `warning` \| `error` |

## Modelli Ollama consigliati (Mac M4)

| Ruolo | Modello | RAM | Comando |
|---|---|---|---|
| Copywriter (LLM) | `llama3.2` | ~3 GB | `ollama pull llama3.2` |
| Visual Expert (LLM) | `gemma4:e4b` | ~5 GB | `ollama pull gemma4:e4b` |
| Image (opzionale) | `x/z-image-turbo` | ~3 GB | `ollama pull x/z-image-turbo` |

Con backend `pollinations` (default) bastano i due modelli LLM: ~8 GB totali, compatibile con Mac M4 da 16 GB.

## MCP — Integrazione con client esterni

Gli endpoint MCP seguono la specifica [Model Context Protocol](https://modelcontextprotocol.io) e sono compatibili con Claude Desktop, Cursor, Continue e altri client MCP.

### Lista tool disponibili

```bash
curl http://localhost:8000/mcp/tools
```

### Eseguire un tool

```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "generate_campaign",
    "parameters": {
      "product": "Hand Cream for Dry Hands",
      "season": "Inverno 2025",
      "audience": "Donne 30-50 anni",
      "best_house_environment": "Bagno minimalista, luce naturale"
    }
  }'
```

### Recuperare l'immagine via MCP

```bash
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_campaign_image",
    "parameters": {
      "image_path": "output/images/background_a3f9c1e2.png"
    }
  }'
```

## Test

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

> I test richiedono Ollama attivo con i modelli `llama3.2` e `gemma4:e4b`.

## Workflow validazione umana

1. Chiama `POST /api/v1/campaign/generate` con il briefing JSON
2. Ricevi **copy** (headline + tagline + testo) → valida e modifica
3. Ricevi **visual** con `image_path` → apri il PNG in `output/images/`
4. Se l'immagine non soddisfa → modifica `POLLINATIONS_MODEL` nel `.env` e ritenta
5. Approva e passa alla produzione