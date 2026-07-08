import logging
from txtai.embeddings import Embeddings
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SemanticIndexer:
    """
    Indexes code structure and documentation using txtai.
    """
    def __init__(self, index_path: str = "index"):
        self.embeddings = Embeddings({
            "path": "BAAI/bge-small-en-v1.5",
            "content": True,
            "hybrid": True
        })
        self.index_path = index_path

    async def index_nodes(self, nodes: List[Dict[str, Any]]):
        """
        Indexes a list of nodes.
        Extracts documentation, function headers, etc.
        """
        data = []
        for node in nodes:
            # Construct a text representation for embedding
            text = f"{node.get('kind')} {node.get('fqn')}\n"
            if node.get("docstring"):
                text += f"Documentation: {node.get('docstring')}\n"
            if node.get("signature"):
                text += f"Signature: {node.get('signature')}\n"

            data.append((node.get("id"), text, None))

        self.embeddings.index(data)
        self.embeddings.save(self.index_path)
        logger.info(f"Indexed {len(data)} nodes at {self.index_path}")

    async def add_node(self, node_id: str, text: str, metadata: Dict[str, Any] = None):
        self.embeddings.upsert([(node_id, text, metadata)])
        self.embeddings.save(self.index_path)
