import pytest
import os
import shutil

# Skip all tests in this module if txtai is not installed
txtai = pytest.importorskip("txtai")

from code_intel.semantic.indexer import SemanticIndexer
from code_intel.semantic.search import SemanticSearch

@pytest.mark.asyncio
async def test_semantic_indexing_and_search():
    index_path = "test_index"
    if os.path.exists(index_path):
        shutil.rmtree(index_path)
        
    indexer = SemanticIndexer(index_path=index_path)
    nodes = [
        {"id": "n1", "kind": "function", "fqn": "auth.login", "docstring": "Handles user login"},
        {"id": "n2", "kind": "function", "fqn": "db.query", "docstring": "Executes a database query"}
    ]
    
    await indexer.index_nodes(nodes)
    
    searcher = SemanticSearch(index_path=index_path)
    results = await searcher.search("How to login?")
    
    assert len(results) > 0
    assert results[0]["id"] == "n1"
    
    if os.path.exists(index_path):
        shutil.rmtree(index_path)
