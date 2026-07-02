"""
Brief Extractor Agent.
Receives a briefing PDF file, reads it, and uses Ollama to extract
a structured JSON with the fields required by BriefingJson.
"""
import json
import logging
import re
import time
from io import BytesIO
import httpx
import fitz  # pymupdf
import openpyxl

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
  "brand": "FullCosmetics — The Force of Beauty",
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


def _extract_data_from_excel(excel_bytes: bytes, filename: str) -> tuple[dict, str]:
    try:
        workbook = openpyxl.load_workbook(BytesIO(excel_bytes), data_only=True)
    except Exception as e:
        logger.error("  [BRIEF EXTRACTOR] ✗ Excel read error: %s", e)
        raise ValueError(f"Impossibile leggere il file Excel: {e}")

    sheet = workbook.active
    raw_rows = []
    values: dict[str, str] = {}
    urls: list[str] = []

    for row in sheet.iter_rows(values_only=True):
        cells = [str(cell).strip() if cell is not None else "" for cell in row]
        if any(cells):
            raw_rows.append(" | ".join([c for c in cells if c]))

        for i in range(0, len(cells), 2):
            key = cells[i]
            value = cells[i + 1] if i + 1 < len(cells) else ""
            if key:
                values[key] = value

        for cell in cells:
            if cell and cell.lower().startswith("http"):
                urls.append(cell)

    def _get(*keys: str) -> str | None:
        for key in keys:
            value = values.get(key)
            if value:
                return str(value).strip()
        return None

    raw_text = "\n".join(raw_rows)
    product = _get("Product", "Product Name")
    campaign_name = _get("Campaign Name")
    brand = _get("Brand")
    season = _get("Season / Period", "Season")
    audience = _get("Target Audience")
    goal = _get("Campaign Objective", "Objective", "Campaign Objectives")
    tone_of_voice = _get("Tone of Voice", "Tone of voice")
    key_messages_raw = _get("Key Messages", "Key message")
    product_url = _get("Product Image (OneDrive)", "Product URL", "Product Link")

    if not product_url and urls:
        product_url = next((u for u in urls if "product" in u.lower()), urls[0])

    key_messages = None
    if key_messages_raw:
        lines = [line.strip() for line in re.split(r"[\n\r]+", str(key_messages_raw)) if line.strip()]
        key_messages = [re.sub(r"^[•\-\*\s]+", "", line).strip() for line in lines if line.strip()]

    return (
        {
            "product": product,
            "product_url": product_url,
            "season": season,
            "audience": audience,
            "goal": goal,
            "tone_of_voice": tone_of_voice,
            "brand": brand,
            "campaign_name": campaign_name,
            "key_messages": key_messages,
        },
        raw_text,
    )


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


async def run_generate_brief_json(file_bytes: bytes, filename: str) -> BriefingJson:
    t0 = time.perf_counter()

    logger.info(SEPARATOR)
    logger.info("▶  BRIEF EXTRACTOR — Starting extraction")
    logger.info("   File     : %s (%.1f KB)", filename, len(file_bytes) / 1024)
    logger.info("   LLM      : %s", settings.ollama_llm_model)

    if filename.lower().endswith(".xlsx"):
        logger.info("   Step 1/3 — Extracting data from Excel…")
        extracted_dict, raw_text = _extract_data_from_excel(file_bytes, filename)
        extracted_dict["raw_extraction"] = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text
    else:
        logger.info("   Step 1/3 — Extracting text from PDF…")
        raw_text = _extract_text_from_pdf(file_bytes)

        if len(raw_text.strip()) < 50:
            raise ValueError(
                "PDF appears empty or has no readable text. "
                "Check it's not a scanned image without OCR."
            )

        MAX_CHARS = 12000
        if len(raw_text) > MAX_CHARS:
            logger.warning(
                "   ⚠ PDF text truncated from %d to %d chars (context limit)",
                len(raw_text), MAX_CHARS,
            )
            raw_text = raw_text[:MAX_CHARS] + "\n\n[... truncated ...]"

        logger.info("   Step 2/3 — Calling LLM for structured extraction (%d chars)…", len(raw_text))
        user_message = f"""Please analyze the following campaign brief and extract the structured information as a valid JSON object.

    BRIEF CONTENT:
    {raw_text}
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

        logger.info("   Step 3/3 — Parsing and validating JSON…")
        try:
            extracted_dict = _parse_json_from_response(raw_response)
        except ValueError as e:
            logger.error("   ✗ JSON parse failed: %s", e)
            raise ValueError(f"Model did not return valid JSON: {e}")

        extracted_dict["raw_extraction"] = raw_text[:500] + "..." if len(raw_text) > 500 else raw_text

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
