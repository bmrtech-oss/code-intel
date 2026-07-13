import logging
from typing import List, Any

logger = logging.getLogger(__name__)

class TestMapper:
    __test__ = False
    """
    Maps code symbols to their corresponding test files.
    Uses call-site analysis from the topological engine.
    """
    def __init__(self, adapter: Any):
        self.adapter = adapter

    async def get_tests_for_symbol(self, symbol_fqn: str, commit_sha: str) -> List[str]:
        """
        Finds tests that call the given symbol directly or indirectly.
        Identifies tests by looking for symbols in files that match test patterns.
        """
        # 1. Get all callers of the target symbol
        all_calls = await self.adapter.get_calls(commit_sha)
        
        # 2. Filter callers that are likely tests
        # We define "likely tests" as symbols defined in files containing 'test'
        # or having 'test_' prefix/suffix.
        test_files = set()
        
        # Direct callers
        direct_callers = [c["from"] for c in all_calls if c["to"] == symbol_fqn]
        
        # To handle indirect callers (transitive impact), we could use the blast radius.
        # But for simple mapping, we look at who calls it.
        
        # 3. Resolve caller FQNs to files
        all_symbols = await self.adapter.get_symbols(commit_sha)
        symbol_map = {s["fqn"]: s for s in all_symbols}
        
        for caller_fqn in direct_callers:
            symbol = symbol_map.get(caller_fqn)
            if symbol:
                file_path = symbol.get("file", "")
                if self._is_test_file(file_path):
                    test_files.add(file_path)
                    
        return list(test_files)

    def _is_test_file(self, file_path: str) -> bool:
        """Heuristic to determine if a file is a test file."""
        p = file_path.lower()
        return "test" in p or "spec" in p
