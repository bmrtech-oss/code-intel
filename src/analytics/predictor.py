import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ImpactPredictor:
    """
    Predicts the impact blast radius of code modifications based on
    historical structural coupling (co-modification patterns).
    """
    def __init__(self, adapter: Any):
        self.adapter = adapter

    async def predict_blast_radius(self, symbol_fqn: str, commit_sha: str) -> Dict[str, Any]:
        """
        Calculates predicted impact based on call graph AND historical co-modifications.
        """
        # 1. Get structural dependencies (direct callers)
        direct_callers = await self.adapter.get_calls(commit_sha)
        structural_impact = {c["from"] for c in direct_callers if c["to"] == symbol_fqn}
        
        # 2. Get historical co-modifications
        # Fetch all symbols visible at this commit
        all_symbols = await self.adapter.get_symbols(commit_sha)
        target_node = next((s for s in all_symbols if s["fqn"] == symbol_fqn), None)
        
        historical_impact = set()
        if target_node:
            target_mod_shas = set(target_node.get("modified_in", []) or [])
            
            for node in all_symbols:
                if node["fqn"] == symbol_fqn:
                    continue
                
                node_mod_shas = set(node.get("modified_in", []) or [])
                
                # Filter out None and empty strings
                target_mod_shas_clean = {s for s in target_mod_shas if s}
                node_mod_shas_clean = {s for s in node_mod_shas if s}

                # Intersection: commits where both were modified
                co_mods = target_mod_shas_clean.intersection(node_mod_shas_clean)
                if len(co_mods) > 0:
                    # Strength of coupling could be weight based on len(co_mods)
                    historical_impact.add(node["fqn"])

        return {
            "symbol": symbol_fqn,
            "structural_callers": list(structural_impact),
            "historical_coupling": list(historical_impact),
            "predicted_blast_radius": list(structural_impact.union(historical_impact))
        }
