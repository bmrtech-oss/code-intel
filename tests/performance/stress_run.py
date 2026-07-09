import asyncio
import time
import logging
from git import Repo
from src.core.git_handler import GitRepoHandler
from src.storage.bitemporal_adapter import BiTemporalAdapter
from src.storage.graph_engine import SimpleGraphEngine
from src.cache.memory_cache import MemoryCache
from src.cache.cache_bootstrap import CacheBootstrap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_stress_test(repo_url: str, num_queries: int = 100):
    logger.info(f"Cloning {repo_url} for stress test...")
    handler = GitRepoHandler(repo_url)
    repo_path = handler.clone()
    
    try:
        repo = Repo(repo_path)
        commits = list(repo.iter_commits())
        logger.info(f"Repository has {len(commits)} commits.")
        
        # In a real stress test, we would index all these commits.
        # For this script, we'll simulate a deep history by querying random points in the DAG.
        
        engine = SimpleGraphEngine() # Uses nodes.jsonl edges.jsonl
        # If they don't exist, we'll just mock them for the test
        if not engine.nodes:
            engine.commits = [{"sha": c.hexsha, "parents": [p.hexsha for p in c.parents]} for c in commits]
            engine.sha_to_bit = {c["sha"]: i for i, c in enumerate(reversed(engine.commits))}
            engine.ancestry_masks = engine._build_ancestry_masks()
            engine.nodes = [{"id": f"n{i}", "introduced_in": commits[-1].hexsha} for i in range(1000)]
            engine.edges = [{"from": f"n{i}", "to": f"n{i+1}", "introduced_in": commits[-1].hexsha} for i in range(999)]
            engine._calculate_bits()

        cache = MemoryCache()
        adapter = BiTemporalAdapter(engine, cache)
        
        # Warm up cache with latest commit
        bootstrap = CacheBootstrap(engine, cache)
        await bootstrap.initialize_cache()
        
        start_time = time.time()
        logger.info(f"Starting {num_queries} topological lookback queries...")
        
        for i in range(num_queries):
            # Pick a commit from different points in history
            target_commit = commits[i % len(commits)].hexsha
            
            q_start = time.perf_counter()
            symbols = await adapter.get_symbols(target_commit)
            q_duration = (time.perf_counter() - q_start) * 1000
            
            if i % 10 == 0:
                logger.info(f"Query {i}: {len(symbols)} symbols found in {q_duration:.2f}ms")
        
        total_duration = time.time() - start_time
        logger.info(f"Stress test complete. Total time: {total_duration:.2f}s")
        logger.info(f"Average query time: {(total_duration/num_queries)*1000:.2f}ms")
        
    finally:
        handler.cleanup()

if __name__ == "__main__":
    # Use a well-known repo with long history for testing (e.g., git itself or a smaller one)
    # For CI/CD we might use a mock repo
    repo_url = "https://github.com/pallets/flask.git"
    asyncio.run(run_stress_test(repo_url))
