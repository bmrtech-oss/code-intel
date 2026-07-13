import pytest
from unittest.mock import AsyncMock
from code_intel.lang.cs_handler import CSharpVisitor

@pytest.mark.asyncio
async def test_cs_handler():
    storage = AsyncMock()
    # Path to the example C# file
    file_path = "examples/csharp/Program.cs"
    
    visitor = CSharpVisitor(storage, file_path, "v1")
    await visitor.parse()
    
    # Check if symbols are inserted
    calls = storage.insert_symbol.call_args_list
    names = [call.args[1] for call in calls]
    
    assert "Program" in names
    assert "Main" in names
    assert "SayHello" in names
