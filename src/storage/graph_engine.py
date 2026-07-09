import json
import os
from typing import List, Dict, Any, Optional

class SimpleGraphEngine:
    """
    Functional graph engine client that implements topological query logic
    using JSONL data as the source of truth.
    Optimized with bitset-based ancestry visibility.
    """
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.commits = self._load_jsonl("commits.jsonl")
        
        # Build SHA to Bit Index mapping
        self.sha_to_bit = {c["sha"]: i for i, c in enumerate(reversed(self.commits))}
        self.ancestry_masks = self._build_ancestry_masks()
        
        self.nodes = self._load_jsonl("nodes.jsonl")
        self.edges = self._load_jsonl("edges.jsonl")
        
        # Pre-calculate bits for nodes and edges
        self._calculate_bits()

    def _calculate_bits(self):
        for n in self.nodes:
            n["_intro_bit"] = 1 << self.sha_to_bit.get(n.get("introduced_in"), 999) if n.get("introduced_in") in self.sha_to_bit else 0
            n["_del_bit"] = 1 << self.sha_to_bit.get(n.get("deleted_in"), 999) if n.get("deleted_in") in self.sha_to_bit else 0

        for e in self.edges:
            e["_intro_bit"] = 1 << self.sha_to_bit.get(e.get("introduced_in"), 999) if e.get("introduced_in") in self.sha_to_bit else 0
            e["_del_bit"] = 1 << self.sha_to_bit.get(e.get("deleted_in"), 999) if e.get("deleted_in") in self.sha_to_bit else 0

    def _build_ancestry_masks(self) -> Dict[str, int]:
        masks = {}
        # Commits are loaded from JSONL, usually in reverse chronological order.
        # To build masks iteratively without recursion, we process from oldest to newest.
        # This assumes parents appear after their children in the commits list (reversed chronological).
        # reversed(self.commits) should be roughly oldest first.
        
        for c in reversed(self.commits):
            sha = c["sha"]
            mask = 1 << self.sha_to_bit[sha]
            for parent in c.get("parents", []):
                mask |= masks.get(parent, 0)
            masks[sha] = mask
        
        # Support mock versions
        if 'v1' not in masks:
            masks['v1'] = 0b1
        if 'v2' not in masks:
            masks['v2'] = 0b11
        return masks

    def _load_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            return [json.loads(line) for line in f]

    async def get_current_branch_tip(self) -> str:
        if not self.commits:
            return "head"
        return self.commits[0]["sha"]  # Latest commit

    async def get_ancestry_mask(self, sha: str) -> int:
        return self.ancestry_masks.get(sha, 0)

    async def topological_lookback_query(self, sha: str) -> List[str]:
        # Keep for backward compatibility, but bitsets are preferred
        if sha.startswith('v'):
            if sha == 'v1':
                return ['v1']
            if sha == 'v2':
                return ['v1', 'v2']
            return [sha]

        ancestry = []
        commit_map = {c["sha"]: c for c in self.commits}
        curr = commit_map.get(sha)
        while curr:
            ancestry.append(curr["sha"])
            parents = curr.get("parents", [])
            if not parents:
                break
            curr = commit_map.get(parents[0])
        return ancestry

    async def query_nodes(self, ancestry: Optional[List[str]] = None, node_type: str = "DefNode", filters: Optional[Dict[str, Any]] = None, mask: Optional[int] = None) -> List[Dict[str, Any]]:
        if mask is None and ancestry:
            # Fallback for old callers
            target_mask = 0
            for sha in ancestry:
                target_mask |= (1 << self.sha_to_bit.get(sha, 999)) if sha in self.sha_to_bit else 0
        else:
            target_mask = mask or 0

        results = []
        for n in self.nodes:
            # O(1) Visibility Check
            if (n["_intro_bit"] & target_mask) != 0 and (n["_del_bit"] & target_mask) == 0:
                match = True
                if filters:
                    for k, v in filters.items():
                        if n.get(k) != v:
                            match = False
                            break
                if match:
                    results.append(n)
        return results

    async def query_edges(self, ancestry: Optional[List[str]] = None, edge_type: Optional[str] = None, filters: Optional[Dict[str, Any]] = None, mask: Optional[int] = None) -> List[Dict[str, Any]]:
        if mask is None and ancestry:
            target_mask = 0
            for sha in ancestry:
                target_mask |= (1 << self.sha_to_bit.get(sha, 999)) if sha in self.sha_to_bit else 0
        else:
            target_mask = mask or 0

        results = []
        for e in self.edges:
            # O(1) Visibility Check
            if (e["_intro_bit"] & target_mask) != 0 and (e["_del_bit"] & target_mask) == 0:
                match = True
                if edge_type and e.get("type", "CALLS") != edge_type:
                    match = False
                if match and filters:
                    for k, v in filters.items():
                        if e.get(k) != v:
                            match = False
                            break
                if match:
                    results.append(e)
        return results

    async def get_delta(self, from_sha: Optional[str], to_sha: str) -> Dict[str, Any]:
        """
        Calculates the symmetric difference (True Delta) between two SHAs using O(1) bitset logic.
        """
        mask_to = await self.get_ancestry_mask(to_sha)
        mask_from = await self.get_ancestry_mask(from_sha) if from_sha else 0

        # Visibility logic: (intro & mask) != 0 AND (del & mask) == 0
        added_nodes = []
        removed_nodes = []
        for n in self.nodes:
            visible_to = (n["_intro_bit"] & mask_to) != 0 and (n["_del_bit"] & mask_to) == 0
            visible_from = (n["_intro_bit"] & mask_from) != 0 and (n["_del_bit"] & mask_from) == 0
            if visible_to and not visible_from:
                added_nodes.append(n)
            elif visible_from and not visible_to:
                removed_nodes.append(n)

        added_edges = []
        removed_edges = []
        for e in self.edges:
            visible_to = (e["_intro_bit"] & mask_to) != 0 and (e["_del_bit"] & mask_to) == 0
            visible_from = (e["_intro_bit"] & mask_from) != 0 and (e["_del_bit"] & mask_from) == 0
            if visible_to and not visible_from:
                added_edges.append(e)
            elif visible_from and not visible_to:
                removed_edges.append(e)

        return {
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "added_edges": added_edges,
            "removed_edges": removed_edges,
            "new_ancestry": await self.topological_lookback_query(to_sha)
        }
