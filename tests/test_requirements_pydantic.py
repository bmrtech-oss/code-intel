import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.core.udf import LLMUDF, RequirementResponse

@pytest.mark.asyncio
async def test_generate_requirements_validation():
    udf = LLMUDF()
    
    # Mock Ollama client
    udf.client.generate = AsyncMock()
    
    # Sample valid response that matches RequirementResponse schema
    valid_json = {
        "epic": "Test Epic",
        "feature": "Test Feature",
        "user_story": "As a dev, I want tests",
        "acceptance_criteria": ["Test passes"],
        "tasks": [
            {"text": "Write test", "traceability": ["func1"]}
        ]
    }
    
    mock_response = MagicMock()
    mock_response.response = json.dumps(valid_json)
    udf.client.generate.return_value = mock_response
    
    symbols = [{"id": 1, "name": "func1"}]
    calls = []
    
    result = await udf.generate_requirements(symbols, calls)
    
    # Ensure it parsed correctly
    assert result["result"]["epic"] == "Test Epic"
    assert "error" not in result["result"]
    
    # Verify it validates against Pydantic
    RequirementResponse.model_validate(result["result"])

@pytest.mark.asyncio
async def test_generate_requirements_fallback():
    udf = LLMUDF()
    udf.client.generate = AsyncMock()
    
    # Response with extra text (should trigger fallback)
    raw_response = "Here is your JSON: " + json.dumps({
        "epic": "Fallback",
        "feature": "Repair",
        "user_story": "story",
        "acceptance_criteria": [],
        "tasks": []
    })
    
    mock_response = MagicMock()
    mock_response.response = raw_response
    udf.client.generate.return_value = mock_response
    
    result = await udf.generate_requirements([], [])
    assert result["result"]["epic"] == "Fallback"
    assert "error" not in result["result"]
