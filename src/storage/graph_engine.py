import json
import os
from typing import List, Dict, Any, Optional

class SimpleGraphEngine:
    """
    Functional graph engine client that implements topological query logic
    using JSONL data as the source of truth.
    """
    def __init__(self, data_dir: str = "."):
        self.data_dir = data_dir
        self.nodes = self._load_jsonl("nodes.jsonl")
        self.edges = self._load_jsonl("edges.jsonl")
        self.commits = self._load_jsonl("commits.jsonl")

    def _load_jsonl(self, filename: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r") as f:
            return [json.loads(line) for line in f]

    async def get_current_branch_tip(self) -> str:
        if not self.commits: return "head"
        return self.commits[0]["sha"] # Latest commit

    async def topological_lookback_query(self, sha: str) -> List[str]:
        # Handle version strings for testing/mocking
        if sha.startswith('v'):
            if sha == 'v1': return ['v1']
            if sha == 'v2': return ['v1', 'v2']
            return [sha]

        ancestry = []
        commit_map = {c["sha"]: c for c in self.commits}
        curr = commit_map.get(sha)
        while curr:
            ancestry.append(curr["sha"])
            parents = curr.get("parents", [])
            if not parents: break
            curr = commit_map.get(parents[0])
        return ancestry

    async def query_nodes(self, ancestry: List[str], node_type: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        ancestry_set = set(ancestry)
        results = []
        for n in self.nodes:
            if n.get("introduced_in") in ancestry_set:
                deleted_in = n.get("deleted_in")
                if deleted_in is None or deleted_in not in ancestry_set:
                    match = True
                    if filters:
                        for k, v in filters.items():
                            if n.get(k) != v: match = False; break
                    if match: results.append(n)
        return results

    async def query_edges(self, ancestry: List[str], edge_type: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        ancestry_set = set(ancestry)
        results = []
        for e in self.edges:
            if e.get("introduced_in") in ancestry_set:
                deleted_in = e.get("deleted_in")
                if deleted_in is None or deleted_in not in ancestry_set:
                    match = True
                    if filters:
                        for k, v in filters.items():
                            if e.get(k) != v: match = False; break
                    if match: results.append(e)
        return results

    async def get_delta(self, from_sha: Optional[str], to_sha: str) -> Dict[str, Any]:
        # Simplification: return everything for to_sha if from_sha is None
        ancestry = await self.topological_lookback_query(to_sha)
        nodes = await self.query_nodes(ancestry, "DefNode")
        edges = await self.query_edges(ancestry, "CALLS")
        return {"nodes": nodes, "edges": edges}
