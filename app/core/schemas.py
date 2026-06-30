from pydantic import BaseModel, Field
from typing import Optional


class ColorPaletteEntry(BaseModel):
    name: Optional[str] = Field(None, description="Display name of the color")
    hex: Optional[str] = Field(None, description="Hex value of the color")


class BriefingInput(BaseModel):
    """Input JSON extracted from campaign briefing."""
    product: Optional[str] = Field(..., description="Name/description of the product")
    season: Optional[str] = Field(..., description="Season/period of the campaign")
    audience: Optional[str] = Field(..., description="Target audience")
    goal: Optional[str] = Field(..., description="Goal of the campaign")
    tone_of_voice: Optional[str] = Field(..., description="Tone of voice of the campaign")

    brand: Optional[str] = Field(None, description="Brand or company")
    campaign_name: Optional[str] = Field(None, description="Name of the campaign")
    key_messages: Optional[list[str]] = Field(None, description="Key messages from the brief")
    color_palette: Optional[list[ColorPaletteEntry]] = Field(
        default_factory=list,
        description="User-selected palette colors sent from the frontend",
    )
    raw_extraction: Optional[str] = Field(None, description="raw text extracted from the PDF")

    model_config = {"populate_by_name": True}


class CopyResult(BaseModel):
    copy_text: str
    headline: str
    tagline: str


class VisualResult(BaseModel):
    image_prompt: Optional[str] = None
    image_base64: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    generation_status: Optional[str] = None
    generation_model: Optional[str] = None


class CampaignOutput(BaseModel):
    briefing: BriefingInput
    copy: CopyResult
    visual: VisualResult
    status: str = "completed"


class CopyOnlyOutput(BaseModel):
    copy: CopyResult
    status: str = "copy_generated"


class VisualOnlyOutput(BaseModel):
    visual: VisualResult
    status: str = "visual_generated"


class BriefingOriginalDocInput(BaseModel):
    """Input: original briefing document (PDF upload).
    Note: the file is received as FastAPI UploadFile, not via Pydantic.
    This schema is used only for OpenAPI documentation.
    """
    model_config = {"populate_by_name": True}

class BriefingJson(BaseModel):
    """Output: structured valid JSON extracted from the original briefing."""
    product: Optional[str] = Field(..., description="Name/description of the product")
    season: Optional[str] = Field(..., description="Season/period of the campaign")
    audience: Optional[str] = Field(..., description="Target audience")
    goal: Optional[str] = Field(..., description="Goal of the campaign")
    tone_of_voice: Optional[str] = Field(..., description="Tone of voice of the campaign")

    brand: Optional[str] = Field(None, description="Brand or company")
    campaign_name: Optional[str] = Field(None, description="Name of the campaign")
    key_messages: Optional[list[str]] = Field(None, description="Key messages from the brief")
    color_palette: Optional[list[ColorPaletteEntry]] = Field(
        default_factory=list,
        description="User-selected palette colors sent from the frontend",
    )
    raw_extraction: Optional[str] = Field(None, description="raw text extracted from the PDF")

    model_config = {"populate_by_name": True}
