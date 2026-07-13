import pytest
import os
from unittest.mock import AsyncMock
from code_intel.lang.python_handler import PythonVisitor

@pytest.mark.asyncio
async def test_python_confidence():
    storage = AsyncMock()
    # Create a temporary python file with various call types
    content = """
def direct_call():
    pass

def test():
    direct_call()
    obj.method_call()
    getattr(obj, "dynamic")
    eval("1+1")
"""
    with open("temp_test_conf.py", "w") as f:
        f.write(content)
    
    try:
        visitor = PythonVisitor(storage, "temp_test_conf.py", "v1")
        await visitor.parse()
        
        # storage.insert_call(caller, callee, confidence, version)
        calls = storage.insert_call.call_args_list
        # The callee text for obj.method_call() is "obj.method_call"
        confidences = {call.args[1]: call.args[2] for call in calls}
        
        assert confidences["direct_call"] == 1.0
        assert confidences["obj.method_call"] == 0.5
        assert confidences["getattr"] == 0.3
        assert confidences["eval"] == 0.3
    finally:
        if os.path.exists("temp_test_conf.py"):
            os.remove("temp_test_conf.py")
