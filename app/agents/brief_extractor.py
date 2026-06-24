"""
Brief Extractor Agent
Riceve un file PDF di briefing, lo legge, e usa Ollama (llama3.2) per estrarre
un JSON strutturato con i campi richiesti da BriefingJson.

Flusso:
  1. Legge il testo dal PDF tramite pymupdf (fitz)
  2. Invia il testo a Ollama con un prompt di estrazione
  3. Parsa il JSON restituito e valida con Pydantic BriefingJson
"""
import json
import logging
import re
import httpx
import fitz  # pymupdf

from app.core.config import settings
from app.core.schemas import BriefingJson

logger = logging.getLogger(__name__)

BRIEF_EXTRACTOR_SYSTEM_PROMPT = """You are a strategic marketing analyst specialized in extracting structured data from advertising campaign briefs.

Your task is to read the provided brief document and extract the following information, returning ONLY a valid JSON object.

EXTRACTION RULES:
- "product": the specific product or product line being advertised (be specific, e.g. "Moisturizing Hand Cream 50ml" not just "cream")
- "season": the campaign season or time period (e.g. "Winter 2025", "Q1 2026", "Summer Campaign")
- "audience": the target audience description (demographics, psychographics, lifestyle)
- "goal": the goal of the campaign
- "tone_of_voice": the tone of the words used for the campaign
- "brand": the brand or company name if mentioned
- "campaign_name": the campaign name or title if explicitly stated
- "key_messages": a list of 2-4 key messages or claims from the brief
- "raw_extraction": the raw text of the brief file

If a field cannot be determined from the brief, use null.

Respond ONLY with a valid JSON object — no markdown, no explanation, no code blocks.

Example output:
{
  "product": "Regenerating Night Cream",
  "season": "Winter 2025",
  "audience": "Women 35-55, skin-conscious, premium lifestyle",
  "goal": "Elegant bathroom with warm ambient light",
  "tone_of_voice": "Warm, reassuring, premium, and comforting",
  "brand": "Dermalab",
  "campaign_name": "Winter Ritual",
  "key_messages": ["Deep regeneration overnight", "Clinically tested formula", "Luxury skincare ritual"],
  "raw_extraction": "....."
}
"""


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Estrae tutto il testo dal PDF usando pymupdf."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")
        doc.close()
        full_text = "\n\n".join(text_parts)
        logger.info(
            "Brief Extractor: estratti %d caratteri da %d pagine PDF",
            len(full_text), len(text_parts)
        )
        return full_text
    except Exception as e:
        logger.error("Brief Extractor: errore lettura PDF: %s", e)
        raise ValueError(f"Impossibile leggere il PDF: {e}")


def _parse_json_from_response(raw: str) -> dict:
    """
    Estrae il JSON dalla risposta del modello.
    Gestisce casi in cui il modello avvolge il JSON in markdown code blocks.
    """
    # Rimuovi eventuali ```json ... ``` o ``` ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

    # Tenta parsing diretto
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Tenta di trovare il primo oggetto JSON nel testo
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Nessun JSON valido trovato nella risposta del modello: {raw[:300]}")


async def run_generate_brief_json(pdf_bytes: bytes, filename: str) -> BriefingJson:
    """
    Punto d'ingresso principale.
    Riceve i bytes del PDF, estrae il testo, chiama Ollama e restituisce BriefingJson.
    """
    logger.info("Brief Extractor: avvio estrazione da '%s'", filename)

    # 1. Estrai testo dal PDF
    pdf_text = _extract_text_from_pdf(pdf_bytes)

    if len(pdf_text.strip()) < 50:
        raise ValueError(
            "Il PDF sembra vuoto o non contiene testo leggibile. "
            "Verifica che non sia un PDF scansionato (immagine senza OCR)."
        )

    # Tronca il testo se troppo lungo per il contesto del modello (~12.000 char)
    MAX_CHARS = 12000
    if len(pdf_text) > MAX_CHARS:
        logger.warning(
            "Brief Extractor: testo PDF troncato da %d a %d caratteri",
            len(pdf_text), MAX_CHARS
        )
        pdf_text = pdf_text[:MAX_CHARS] + "\n\n[... documento troncato per limiti di contesto ...]"

    # 2. Prepara la chiamata a Ollama
    user_message = f"""Please analyze the following campaign brief and extract the structured information as a valid JSON object.

    BRIEF CONTENT:
    {pdf_text}
    """

    payload = {
        "model": settings.ollama_llm_model,
        "messages": [
            {"role": "system", "content": BRIEF_EXTRACTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,   # bassa temperatura per output deterministico
            "top_p": 0.9,
        },
    }

    logger.info(
        "Brief Extractor: chiamata Ollama '%s' con %d caratteri di brief",
        settings.ollama_llm_model, len(pdf_text)
    )

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        raw_response = data.get("message", {}).get("content", "")
        logger.info("Brief Extractor: risposta Ollama ricevuta (%d char)", len(raw_response))
        logger.debug("Brief Extractor raw response: %s", raw_response[:500])

    except httpx.HTTPStatusError as e:
        logger.error("Brief Extractor: Ollama HTTP error %s: %s", e.response.status_code, e.response.text)
        raise RuntimeError(f"Errore chiamata Ollama: {e.response.status_code}")
    except httpx.TimeoutException:
        logger.error("Brief Extractor: timeout Ollama (120s)")
        raise RuntimeError("Timeout Ollama durante l'estrazione del brief. Riprova.")

    # 3. Parsa e valida il JSON
    try:
        extracted_dict = _parse_json_from_response(raw_response)
    except ValueError as e:
        logger.error("Brief Extractor: parsing JSON fallito: %s", e)
        raise ValueError(f"Il modello non ha restituito un JSON valido: {e}")

    # 4. Aggiungi il testo grezzo per trasparenza/debug
    extracted_dict["raw_extraction"] = pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text

    # 5. Valida con Pydantic
    try:
        result = BriefingJson(**extracted_dict)
        logger.info(
            "Brief Extractor: estrazione completata ✓ — product='%s', season='%s'",
            result.product, result.season
        )
        return result
    except Exception as e:
        logger.error("Brief Extractor: validazione Pydantic fallita: %s — dict: %s", e, extracted_dict)
        raise ValueError(f"I dati estratti non sono validi: {e}")