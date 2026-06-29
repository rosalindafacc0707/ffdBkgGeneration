from fastapi.testclient import TestClient

from main import app
from app.mcp import server as mcp_server
from app.core.schemas import BriefingInput, CampaignOutput, CopyResult, VisualResult


client = TestClient(app)


def test_list_tools_includes_backend_services():
    response = client.get("/mcp/tools")
    assert response.status_code == 200

    tool_names = {tool["name"] for tool in response.json()["tools"]}
    expected = {
        "extract_brief_from_pdf",
        "generate_campaign",
        "generate_copy",
        "generate_background",
        "get_campaign_image",
        "health_check",
    }
    assert expected.issubset(tool_names)


def test_generate_campaign_tool_dispatch(monkeypatch):
    async def fake_run_campaign(briefing: BriefingInput) -> CampaignOutput:
        return CampaignOutput(
            briefing=briefing,
            copy=CopyResult(headline="Hello", tagline="World", copy_text="Body"),
            visual=VisualResult(image_prompt="Prompt", image_path="/tmp/out.png"),
            status="completed",
        )

    monkeypatch.setattr(mcp_server, "run_campaign", fake_run_campaign)

    response = client.post(
        "/mcp/call",
        json={
            "tool_name": "generate_campaign",
            "parameters": {
                "product": "Cream",
                "season": "Summer",
                "audience": "Adults",
                "goal": "Awareness",
                "tone_of_voice": "Friendly",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result"]["status"] == "completed"
