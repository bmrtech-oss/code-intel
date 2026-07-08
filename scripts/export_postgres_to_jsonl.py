import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from git import Repo

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/codeintel")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def fetch_all_facts(session: AsyncSession):
    result = await session.execute(text("SELECT * FROM facts ORDER BY entity_id, valid_from ASC"))
    return result.mappings().all()

async def fetch_all_symbols(session: AsyncSession):
    # Depending on how symbols are used, we might need them or just facts
    result = await session.execute(text("SELECT * FROM symbols ORDER BY id, version ASC"))
    return result.mappings().all()

def get_git_commits(repo_path: str):
    repo = Repo(repo_path)
    commits = []
    for commit in repo.iter_commits():
        commits.append({
            "sha": commit.hexsha,
            "parents": [p.hexsha for p in commit.parents],
            "branch": getattr(commit, 'active_branch', 'main'), # Simplification
            "author": commit.author.name,
            "date": commit.authored_datetime.isoformat()
        })
    return commits

def process_facts_to_nodes_and_edges(facts: List[Dict[str, Any]]):
    nodes = {}
    edges = {}

    # Group facts by entity_id
    grouped_facts = {}
    for fact in facts:
        eid = fact["entity_id"]
        if eid not in grouped_facts:
            grouped_facts[eid] = []
        grouped_facts[eid].append(fact)

    # To find which version deleted an entity, we map valid_from timestamps to versions.
    # We use a dict of timestamps to the version that was active AT that time.
    # Since multiple facts might have same valid_from, we just need one of them to get the version.
    timestamp_to_version = {f["valid_from"]: f["version"] for f in facts}

    for eid, entity_facts in grouped_facts.items():
        entity_type = entity_facts[0]["entity_type"]

        # Sort facts by valid_from for this entity
        sorted_entity_facts = sorted(entity_facts, key=lambda x: x["valid_from"])

        # Determine all versions this entity appeared in
        versions_in_order = []
        seen_versions = set()
        for f in sorted_entity_facts:
            if f["version"] not in seen_versions:
                versions_in_order.append(f["version"])
                seen_versions.add(f["version"])

        if not versions_in_order:
            continue

        introduced_in = versions_in_order[0]
        modified_in = versions_in_order[1:]

        # Check for deletion: all facts have a valid_to
        is_deleted = all(f["valid_to"] is not None for f in entity_facts)
        deleted_in = None
        if is_deleted:
            last_valid_to = max(f["valid_to"] for f in entity_facts)
            # The version that deleted it is the version that was introduced when this became valid_to.
            # In the bi-temporal model, when a fact is superseded or deleted, valid_to is set to 'now'.
            # A new fact (if superseding) would have valid_from = 'now'.
            # So we look for any fact in the entire dataset that has valid_from == last_valid_to.
            deleted_in = timestamp_to_version.get(last_valid_to)

        if entity_type == "symbol":
            # Use attributes from the most recent available version
            latest_attrs = {}
            for f in sorted_entity_facts:
                latest_attrs[f["attribute"]] = f["value"]

            nodes[eid] = {
                "id": eid,
                "kind": latest_attrs.get("kind"),
                "fqn": latest_attrs.get("name"),
                "file": latest_attrs.get("file"),
                "docstring": latest_attrs.get("docstring"),
                "signature": latest_attrs.get("signature"),
                "introduced_in": introduced_in,
                "modified_in": modified_in,
                "deleted_in": deleted_in
            }

        elif entity_type == "call":
            latest_attrs = {}
            for f in sorted_entity_facts:
                latest_attrs[f["attribute"]] = f["value"]

            edges[eid] = {
                "from": latest_attrs.get("caller"),
                "to": latest_attrs.get("callee"),
                "introduced_in": introduced_in,
                "deleted_in": deleted_in
            }

        elif entity_type == "cross_repo_import":
            latest_attrs = {}
            for f in sorted_entity_facts:
                latest_attrs[f["attribute"]] = f["value"]

            # For JSONL, we'll store them as a special edge type
            edges[eid] = {
                "type": "IMPORTS_FROM",
                "from": eid.split("->")[0],
                "to": latest_attrs.get("module"),
                "introduced_in": introduced_in,
                "deleted_in": deleted_in
            }

    return list(nodes.values()), list(edges.values())

async def main():
    repo_path = "." # Assume running from repo root

    async with AsyncSessionLocal() as session:
        try:
            facts = await fetch_all_facts(session)
        except Exception as e:
            print(f"Error fetching facts: {e}")
            facts = []

    commits = get_git_commits(repo_path)
    nodes, edges = process_facts_to_nodes_and_edges(facts)

    with open("commits.jsonl", "w") as f:
        for c in commits:
            f.write(json.dumps(c) + "\n")

    with open("nodes.jsonl", "w") as f:
        for n in nodes:
            f.write(json.dumps(n) + "\n")

    with open("edges.jsonl", "w") as f:
        for e in edges:
            f.write(json.dumps(e) + "\n")

    print(f"Exported {len(commits)} commits, {len(nodes)} nodes, and {len(edges)} edges.")

if __name__ == "__main__":
    asyncio.run(main())
