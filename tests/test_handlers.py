import pytest
from unittest.mock import AsyncMock
from code_intel.lang.python_handler import PythonVisitor
from code_intel.lang.ts_handler import TypeScriptVisitor
from code_intel.lang.go_handler import GoVisitor

@pytest.mark.asyncio
async def test_python_handler():
    storage = AsyncMock()
    visitor = PythonVisitor(storage, "tests/golden/python/api.py", "v1")
    await visitor.parse()
    
    # Check if symbols are inserted
    calls = storage.insert_symbol.call_args_list
    names = [call.args[1] for call in calls]
    assert "tests.golden.python.api.APIHandler" in names
    assert "tests.golden.python.api.APIHandler.handle_request" in names
    assert "tests.golden.python.api.dead_function" in names

@pytest.mark.asyncio
async def test_ts_handler():
    storage = AsyncMock()
    visitor = TypeScriptVisitor(storage, "tests/golden/ts/repository.ts", "v1")
    await visitor.parse()
    
    calls = storage.insert_symbol.call_args_list
    names = [call.args[1] for call in calls]
    assert "tests.golden.ts.repository.Repository" in names
    assert "tests.golden.ts.repository.Repository.save" in names

@pytest.mark.asyncio
async def test_go_handler():
    storage = AsyncMock()
    visitor = GoVisitor(storage, "tests/golden/go/main.go", "v1")
    await visitor.parse()
    
    calls = storage.insert_symbol.call_args_list
    names = [call.args[1] for call in calls]
    assert "main.Logger" in names
    assert "main.Logger.Log" in names
    assert "main.DeadGoFunction" in names
