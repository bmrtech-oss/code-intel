import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class CochangePredictor:
    """
    Predicts the 'Likely Next Edit' based on historical temporal coupling.
    Uses an association matrix derived from the topological 'modified_in' metadata.
    """
    def __init__(self, adapter: Any):
        self.adapter = adapter

    async def predict_next_edits(self, symbol_fqn: str, commit_sha: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Identifies files/symbols that historically change together with the target symbol.
        """
        # 1. Fetch all symbols and their modification history
        all_symbols = await self.adapter.get_symbols(commit_sha)
        symbol_map = {s["fqn"]: s for s in all_symbols}
        target_node = symbol_map.get(symbol_fqn)
        
        if not target_node:
            return []

        target_history = set(target_node.get("modified_in", []) or [])
        target_history = {s for s in target_history if s}
        
        if not target_history:
            return []

        predictions = []
        
        # 2. Calculate Jaccard Similarity for temporal coupling
        for node in all_symbols:
            if node["fqn"] == symbol_fqn:
                continue
            
            node_history = set(node.get("modified_in", []) or [])
            node_history = {s for s in node_history if s}
            
            intersection = target_history.intersection(node_history)
            union = target_history.union(node_history)
            
            if not union:
                continue
                
            similarity = len(intersection) / len(union)
            
            if similarity >= threshold:
                predictions.append({
                    "symbol": node["fqn"],
                    "confidence": round(similarity, 3),
                    "reason": f"Historically changed together in {len(intersection)} commits."
                })

        # Sort by confidence
        return sorted(predictions, key=lambda x: x["confidence"], reverse=True)
