"""
Brief Extractor Agent
Riceve un file PDF di briefing, lo legge, e usa Ollama per estrarre
un JSON strutturato con i campi richiesti da BriefingJson.
"""
import json
import logging
import re
import time
import httpx
import fitz  # pymupdf

from app.core.config import settings
from app.core.schemas import BriefingJson

logger = logging.getLogger(__name__)

SEPARATOR = "─" * 60

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
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{text.strip()}")
        doc.close()
        full_text = "\n\n".join(text_parts)
        logger.info("  [BRIEF EXTRACTOR]   PDF parsed: %d chars across %d page(s)",
                    len(full_text), len(text_parts))
        return full_text
    except Exception as e:
        logger.error("  [BRIEF EXTRACTOR] ✗ PDF read error: %s", e)
        raise ValueError(f"Impossibile leggere il PDF: {e}")


def _parse_json_from_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise ValueError(f"No valid JSON in model response: {raw[:300]}")


async def run_generate_brief_json(pdf_bytes: bytes, filename: str) -> BriefingJson:
    t0 = time.perf_counter()

    logger.info(SEPARATOR)
    logger.info("▶  BRIEF EXTRACTOR — Starting extraction")
    logger.info("   File     : %s (%.1f KB)", filename, len(pdf_bytes) / 1024)
    logger.info("   LLM      : %s", settings.ollama_llm_model)

    # 1. Extract text from PDF
    logger.info("   Step 1/3 — Extracting text from PDF…")
    pdf_text = _extract_text_from_pdf(pdf_bytes)

    if len(pdf_text.strip()) < 50:
        raise ValueError(
            "PDF appears empty or has no readable text. "
            "Check it's not a scanned image without OCR."
        )

    MAX_CHARS = 12000
    if len(pdf_text) > MAX_CHARS:
        logger.warning("   ⚠ PDF text truncated from %d to %d chars (context limit)",
                       len(pdf_text), MAX_CHARS)
        pdf_text = pdf_text[:MAX_CHARS] + "\n\n[... truncated ...]"

    # 2. Call Ollama
    logger.info("   Step 2/3 — Calling LLM for structured extraction (%d chars)…", len(pdf_text))
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
        "options": {"temperature": 0.1, "top_p": 0.9},
    }

    t_llm = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_response = data.get("message", {}).get("content", "")
        elapsed_llm = time.perf_counter() - t_llm
        logger.info("   LLM responded in %.1fs (%d chars)", elapsed_llm, len(raw_response))

    except httpx.HTTPStatusError as e:
        logger.error("   ✗ Ollama HTTP %s: %s", e.response.status_code, e.response.text[:200])
        raise RuntimeError(f"Ollama error: {e.response.status_code}")
    except httpx.TimeoutException:
        logger.error("   ✗ Ollama timeout after 120s")
        raise RuntimeError("Timeout calling Ollama. Try again.")

    # 3. Parse & validate
    logger.info("   Step 3/3 — Parsing and validating JSON…")
    try:
        extracted_dict = _parse_json_from_response(raw_response)
    except ValueError as e:
        logger.error("   ✗ JSON parse failed: %s", e)
        raise ValueError(f"Model did not return valid JSON: {e}")

    extracted_dict["raw_extraction"] = pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text

    try:
        result = BriefingJson(**extracted_dict)
    except Exception as e:
        logger.error("   ✗ Pydantic validation failed: %s", e)
        raise ValueError(f"Extracted data is invalid: {e}")

    elapsed = time.perf_counter() - t0
    logger.info("✓  BRIEF EXTRACTOR — Done in %.1fs", elapsed)
    logger.info("   Product       : %s", result.product)
    logger.info("   Season        : %s", result.season)
    logger.info("   Brand         : %s", result.brand or "—")
    logger.info("   Campaign      : %s", result.campaign_name or "—")
    logger.info("   Key messages  : %d found", len(result.key_messages or []))
    logger.info(SEPARATOR)

    return result