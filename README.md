# FullForce Ad Generator 🎯

Sistema agentico per la generazione automatica di background pubblicitari per campagne di prodotti dermatologici e cosmetici.
Basato su **FastAPI** + **LangGraph** + **Ollama** (LLM 100% locale) + **Pollinations.ai** (image generation, gratuito, nessuna subscription).

---

## Architettura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT                                        │
│  POST /campaign/brief_insights_extraction  →  PDF Upload            │
│  POST /campaign/generate                   →  JSON Briefing         │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  COORDINATOR    │  (LangGraph — fan-out parallelo)
                  └────────┬────────┘
                           │
               ┌───────────┴───────────┐
               │                       │
               ▼                       ▼
   ┌─────────────────┐     ┌───────────────────────────────────────┐
   │   COPYWRITER    │     │            VISUAL EXPERT              │
   │  (llama3.2)     │     │  1. gemma4:e4b → prompt FLUX          │
   │                 │     │  2. image_generator                   │
   │  → headline     │     │     → FLUX_NEGATIVE_PREFIX preposto   │
   │  → tagline      │     │     → pollinations_generator          │
   │  → copy_text    │     │  → image_path + base64                │
   └────────┬────────┘     └──────────────────┬────────────────────┘
            │                                 │
            └─────────────┬───────────────────┘
                          │ fan-in
                          ▼
           Output per Validazione Umana
           • copy:   headline + tagline + copy_text
           • visual: image_prompt + image_path + base64
```

---

## Flusso completo con estrazione brief

```
PDF Briefing
    │
    ▼
POST /campaign/brief_insights_extraction
    │  brief_extractor.py
    │  • pymupdf → estrae testo PDF
    │  • llama3.2 → estrae JSON strutturato
    │
    ▼
BriefingJson
{
  "product", "season", "audience", "goal",
  "tone_of_voice", "brand", "campaign_name",
  "key_messages", "raw_extraction"
}
    │
    ▼  (usa i campi obbligatori come input di /campaign/generate)
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

## Prerequisiti

- Python 3.11+
- [Ollama](https://ollama.ai) installato e attivo
- Modelli Ollama da scaricare:

```bash
ollama pull llama3.2       # LLM copywriter + brief extractor
ollama pull gemma4:e4b     # LLM visual expert (costruzione prompt FLUX)
```

> Per la generazione immagini il backend default è **Pollinations.ai** — cloud, gratuito, nessun download necessario.

---

## Setup

```bash
# 1. Virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2. Dipendenze base (include pymupdf per lettura PDF)
pip install -r requirements.txt

# 3. Configurazione
cp .env.example .env
# Verifica IMAGE_BACKEND=pollinations nel .env

# 4. Avvio
python main.py
```

App: **http://localhost:8000** — Swagger UI: **http://localhost:8000/docs**

---

## Backend image generation

Selezionabile via `IMAGE_BACKEND` nel `.env`. Default: `pollinations`.

### `pollinations` — default ✅

Chiama [Pollinations.ai](https://pollinations.ai) via HTTP GET. Gratuito, no API key, no download, no rate limit mensile.

```env
IMAGE_BACKEND=pollinations
POLLINATIONS_MODEL=flux        # flux | flux-realism | flux-anime | turbo
```

| Modello | Stile | Velocità |
|---|---|---|
| `flux` | Qualità alta | ~15-25 sec |
| `flux-realism` | Fotorealistico | ~15-25 sec |
| `flux-anime` | Stile illustrativo | ~15-25 sec |
| `turbo` | Veloce, qualità inferiore | ~5-10 sec |

### Altri backend

| Backend | Requisiti | Note |
|---|---|---|
| `ollama` | Modello image installato localmente | `OLLAMA_IMAGE_MODEL=x/z-image-turbo` |
| `hf_inference` | HF_TOKEN + crediti HF | Piano free esauribile |

---

## FLUX Negative Prefix — anti-allucinazione oggetti

FLUX tende a generare podium e prodotti nelle scene skincare per via del training data.
`image_generator.py` antepone automaticamente un prefisso negativo a tutti i prompt FLUX:

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

Applicato automaticamente su `pollinations` e `hf_inference`. Non va incluso nel prompt di Gemma.

---

## Palette brand obbligatoria

Il `visual_expert.py` usa esclusivamente questi colori:

| Nome | Hex | RGB |
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

## Struttura della repository

```
fullforce_ad_generator/
├── .env.example
├── .gitignore
├── requirements.txt                    ← dipendenze base (include pymupdf)
├── main.py
├── README.md
├── app/
│   ├── core/
│   │   ├── config.py                   ← settings Pydantic (legge .env)
│   │   └── schemas.py                  ← BriefingInput, BriefingJson,
│   │                                      CampaignOutput, VisualResult, CopyResult
│   ├── agents/
│   │   ├── state.py                    ← CampaignState TypedDict per LangGraph
│   │   ├── coordinator.py              ← grafo LangGraph fan-out parallelo
│   │   ├── copywriter.py               ← agente copywriter → headline/tagline/copy
│   │   ├── visual_expert.py            ← agente visual → prompt FLUX via gemma4:e4b
│   │   ├── brief_extractor.py          ← estrae JSON strutturato da PDF via llama3.2
│   │   ├── image_generator.py          ← router backend + FLUX_NEGATIVE_PREFIX
│   │   ├── pollinations_generator.py   ← backend Pollinations.ai (default)
│   │   ├── hf_inference_generator.py   ← backend HuggingFace Inference API
│   ├── api/
│   │   └── routes.py                   ← tutti gli endpoint FastAPI
│   └── mcp/
│       ├── tools.py                    ← definizioni tool MCP
│       └── server.py                   ← GET /mcp/tools  POST /mcp/call
├── output/
│   └── images/                         ← immagini generate (gitignored)
└── tests/
    ├── test_campaign.py
    └── brief_test_dermalab.pdf         ← PDF di esempio per test estrazione brief
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
  "brand": "Dermalab",
  "campaign_name": "Winter Ritual 2025",
  "key_messages": [
    "Deep skin regeneration while you sleep",
    "Clinically tested formula, dermatologist approved",
    "Science-backed: hyaluronic acid + retinol complex"
  ],
  "raw_extraction": "--- Page 1 ---\nCAMPAIGN BRIEF..."
}
```

**Codici di errore:**
- `415` — formato file non supportato (solo PDF)
- `413` — file troppo grande (max 10 MB)
- `422` — testo non estraibile o JSON non valido
- `500` — errore Ollama

---

### `POST /campaign/generate`

Genera copy pubblicitario e immagine background in parallelo.

```bash
curl -X POST http://localhost:8000/api/v1/campaign/generate \
  -H "Content-Type: application/json" \
  -d '{
    "product": "Regenerating Night Cream 50ml",
    "season": "Winter 2025",
    "audience": "Women 35-55, skin-conscious, premium lifestyle",
    "goal": "Increase brand awareness",
    "tone_of_voice": "Sophisticated and reassuring",
    "brand": "Dermalab",
    "campaign_name": "Winter Ritual 2025",
    "key_messages": ["Deep skin regeneration", "Clinically tested"]
  }'
```

**Response:**
```json
{
  "briefing": { "product": "...", "season": "...", "..." },
  "copy": {
    "headline": "Il rituale della notte.",
    "tagline": "Pelle rigenerata. Ogni mattina.",
    "copy_text": "Testo pubblicitario completo..."
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

### `GET /campaign/image/{filename}`

```bash
curl http://localhost:8000/api/v1/campaign/image/background_a3f9c1e2.png \
  --output background.png
```

### Valori `generation_status`

| Status | Significato |
|---|---|
| `generated` | Immagine PNG creata e disponibile |
| `prompt_only` | Modello non supporta image gen, usa `image_prompt` esternamente |
| `error` | Errore durante la generazione, controlla i log |

---

## MCP — Integrazione con client esterni

Compatibile con Claude Desktop, Cursor, Continue e altri client MCP.

```bash
# Lista tool disponibili
curl http://localhost:8000/mcp/tools

# Esegui generazione campagna
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

## Variabili d'ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL server Ollama |
| `OLLAMA_LLM_MODEL` | `llama3.2` | LLM per copywriter e brief extractor |
| `OLLAMA_VISION_MODEL` | `gemma4:e4b` | LLM per costruire il prompt visivo |
| `OLLAMA_IMAGE_MODEL` | `x/z-image-turbo` | Modello image (solo `IMAGE_BACKEND=ollama`) |
| `IMAGE_BACKEND` | `pollinations` | Backend: `pollinations` \| `ollama` \| `hf_inference` |
| `POLLINATIONS_MODEL` | `flux` | Modello Pollinations: `flux` \| `flux-realism` \| `flux-anime` \| `turbo` |
| `HF_TOKEN` | — | Token HuggingFace (solo `hf_inference`) |
| `HF_INFERENCE_MODEL` | `black-forest-labs/FLUX.1-schnell` | Modello HF Inference API |
| `IMAGE_OUTPUT_DIR` | `output/images` | Cartella salvataggio immagini |
| `IMAGE_WIDTH` | `1024` | Larghezza immagine in pixel |
| `IMAGE_HEIGHT` | `768` | Altezza immagine in pixel |
| `APP_HOST` | `0.0.0.0` | Host FastAPI |
| `APP_PORT` | `8000` | Porta FastAPI |
| `LOG_LEVEL` | `info` | Livello log: `debug` \| `info` \| `warning` \| `error` |

---

## Modelli Ollama consigliati (Mac M4)

| Ruolo | Modello | RAM | Comando |
|---|---|---|---|
| Copywriter + Brief Extractor | `llama3.2` | ~3 GB | `ollama pull llama3.2` |
| Visual Expert | `gemma4:e4b` | ~5 GB | `ollama pull gemma4:e4b` |
| Image (opzionale) | `x/z-image-turbo` | ~3 GB | `ollama pull x/z-image-turbo` |

Con backend `pollinations` bastano i due LLM: ~8 GB totali, compatibile con Mac M4 16 GB.

---

## Test

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

> Richiedono Ollama attivo con `llama3.2` e `gemma4:e4b`.
> Per testare `brief_insights_extraction` usa `tests/brief_test_dermalab.pdf`.

---

## Workflow validazione umana

1. **Estrai brief** → `POST /campaign/brief_insights_extraction` con PDF → JSON strutturato
2. **Genera campagna** → `POST /campaign/generate` con JSON → copy + background
3. **Valida copy** → rivedi headline, tagline, copy_text
4. **Valida visual** → apri PNG in `output/images/` — deve essere parete matta vuota con luce diagonale, zero oggetti
5. **Se immagine non soddisfa** → cambia `POLLINATIONS_MODEL` (prova `flux-realism`) e ritenta
6. **Approva e passa in produzione**
