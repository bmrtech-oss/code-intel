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
        # 1. Get structural dependencies (direct callers) with confidence
        direct_callers = await self.adapter.get_calls(commit_sha)
        structural_impact_weighted = {
            c["from"]: c.get("confidence", 1.0) 
            for c in direct_callers if c["to"] == symbol_fqn
        }
        structural_impact = set(structural_impact_weighted.keys())
        
        # 2. Get historical co-modifications
        # Fetch all symbols visible at this commit
        all_symbols = await self.adapter.get_symbols(commit_sha)
        symbol_map = {s["fqn"]: s for s in all_symbols}
        target_node = symbol_map.get(symbol_fqn)
        
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

        # 3. Combine and map to tests
        blast_radius = structural_impact.union(historical_impact)
        
        from .test_mapper import TestMapper
        mapper = TestMapper(self.adapter)
        
        affected_tests = set()
        for affected_symbol in blast_radius:
            tests = await mapper.get_tests_for_symbol(affected_symbol, commit_sha)
            affected_tests.update(tests)
        
        # Also include tests for the target symbol itself
        target_tests = await mapper.get_tests_for_symbol(symbol_fqn, commit_sha)
        affected_tests.update(target_tests)

        return {
            "symbol": symbol_fqn,
            "structural_callers": structural_impact_weighted,
            "historical_coupling": list(historical_impact),
            "predicted_blast_radius": list(blast_radius),
            "affected_tests": list(affected_tests)
        }
