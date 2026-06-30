from app.core.schemas import BriefingInput
from app.agents.visual_expert import build_palette_context


def test_build_palette_context_includes_frontend_palette():
    briefing = BriefingInput(
        product="Hand Cream",
        season="Winter",
        audience="Skincare lovers",
        goal="Promote comfort",
        tone_of_voice="Warm and premium",
        color_palette=[
            {"name": "Sage", "hex": "#6B8E5A"},
            {"name": "Midnight", "hex": "#101820"},
        ],
    )

    context = build_palette_context(briefing)

    assert "Sage #6B8E5A" in context
    assert "Midnight #101820" in context


def test_build_palette_context_falls_back_to_defaults():
    briefing = BriefingInput(
        product="Hand Cream",
        season="Winter",
        audience="Skincare lovers",
        goal="Promote comfort",
        tone_of_voice="Warm and premium",
    )

    context = build_palette_context(briefing)

    assert "Blush #F9EDEF" in context
    assert "Amber #BA6A37" in context
