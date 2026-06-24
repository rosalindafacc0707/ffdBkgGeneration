"""
Test di integrazione per il flusso agentico.
Esegui con: pytest tests/ -v
Richiede Ollama attivo con i modelli configurati in .env
"""
import pytest
from app.core.schemas import BriefingInput
from app.agents.coordinator import run_campaign

SAMPLE_BRIEFING = {
  "product": "Hand Cream for Dry Hands",
  "season": "Autumn 2026",
  "audience": "All genders, 28-60 years old, skincare enthusiasts",
  "goal": "Highlight deep hydration, protection, and comfort against the first autumn cold",
  "tone_of_voice": "Warm, reassuring, premium, and comforting"
}

@pytest.fixture
def briefing():
    return BriefingInput(**SAMPLE_BRIEFING)


@pytest.mark.asyncio
async def test_run_campaign_returns_output(briefing):
    result = await run_campaign(briefing)
    assert result is not None
    assert result.copy is not None
    assert result.visual is not None
    assert result.copy.headline != ""
    assert result.copy.tagline != ""
    assert result.copy.copy_text != ""
    assert result.visual.image_prompt != ""


@pytest.mark.asyncio
async def test_copy_has_all_fields(briefing):
    result = await run_campaign(briefing)
    assert hasattr(result.copy, "headline")
    assert hasattr(result.copy, "tagline")
    assert hasattr(result.copy, "copy_text")


@pytest.mark.asyncio
async def test_visual_has_prompt(briefing):
    result = await run_campaign(briefing)
    assert result.visual.image_prompt
    assert len(result.visual.image_prompt) > 50


@pytest.mark.asyncio
async def test_campaign_status(briefing):
    result = await run_campaign(briefing)
    assert result.status in ["completed", "completed_with_errors"]
