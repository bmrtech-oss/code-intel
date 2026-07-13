import logging
from txtai.embeddings import Embeddings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SemanticSearch:
    """
    Unified search workflow merging lexical and vector similarity.
    """
    def __init__(self, index_path: str = "index"):
        self.embeddings = Embeddings()
        try:
            self.embeddings.load(index_path)
        except Exception as e:
            logger.warning(f"Could not load index from {index_path}: {e}")

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs hybrid search.
        """
        results = self.embeddings.search(query, limit)
        # txtai search returns a list of dicts if content=True
        return results
