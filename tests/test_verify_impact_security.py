import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from code_intel.mcp.server import handle_call_tool

@pytest.mark.asyncio
async def test_verify_impact_security_sanitization():
    # Create mock impact predictor returning safe and unsafe test paths
    mock_predictor = AsyncMock()

    mock_predictor.predict_blast_radius.return_value = {
        "affected_tests": [
            "tests/test_app.py",                         # Safe
            "tests/../malicious.py",                      # Unsafe (path traversal)
            "tests/test_app.py; rm -rf /",                # Unsafe (injection attempt)
            "/absolute/test_file.py",                     # Unsafe (outside sandbox, absolute path)
            "tests/not_a_test_file.py",                   # Unsafe (no test prefix/suffix)
            "tests/test_file.sh"                          # Unsafe (not a .py file)
        ]
    }

    # Patch the global variables and settings
    with patch("code_intel.mcp.server.impact_predictor", mock_predictor):
        with patch("code_intel.mcp.server.USE_BITEMPORAL", True):
            with patch("code_intel.mcp.server.init_topological_stack") as mock_init:
                mock_init.return_value = None

                # Mock subprocess.run to prevent actual execution of pytest during testing
                with patch("subprocess.run") as mock_run:
                    mock_process = MagicMock()
                    mock_process.returncode = 0
                    mock_process.stdout = "passes"
                    mock_process.stderr = ""
                    mock_run.return_value = mock_process

                    # Call handle_call_tool for verify_impact
                    result_contents = await handle_call_tool("verify_impact", {
                        "symbol": "app.main",
                        "commit_sha": "v1"
                    })

                    assert len(result_contents) == 1
                    resp_data = json.loads(result_contents[0].text)

                    test_results = resp_data["test_results"]
                    assert len(test_results) == 6

                    # Verify each result
                    assert test_results[0]["file"] == "tests/test_app.py"
                    assert "error" not in test_results[0]  # Safe file was processed

                    for i in range(1, 6):
                        assert "error" in test_results[i]
                        assert "Unsafe or unauthorized test file path skipped" in test_results[i]["error"]
