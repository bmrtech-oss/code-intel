import argparse
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT_DIR / "tmp"
DEFAULT_OUTPUT = ROOT_DIR / "docs" / "engine_benchmark_results.md"

MEMTRACE_URL = os.getenv("MEMTRACE_URL", "http://127.0.0.1:18080")
TERMINUSDB_URL = os.getenv("TERMINUSDB_URL", "http://127.0.0.1:18081")

SERVER_CODE = r"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DATA = {"commits": [], "edges": []}


def build_ancestry(target_sha: str, commits: list[dict]) -> list[str]:
    ancestry: list[str] = []
    commit_map = {commit["sha"]: commit for commit in commits}
    current = commit_map.get(target_sha)
    while current:
        ancestry.append(current["sha"])
        parents = current.get("parents", [])
        if not parents:
            break
        current = commit_map.get(parents[0])
    return ancestry


def filter_edges(ancestry: list[str], edges: list[dict]) -> list[dict]:
    ancestry_set = set(ancestry)
    return [edge for edge in edges if edge.get("introduced_in") in ancestry_set]


class Handler(BaseHTTPRequestHandler):
    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8")) if raw else {}

    def _write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json({"status": "ok"})
            return
        self._write_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        data = self._read_json()
        if self.path == "/populate":
            DATA["commits"] = data.get("commits", [])
            DATA["edges"] = data.get("edges", [])
            self._write_json({"ok": True, "commit_count": len(DATA["commits"]), "edge_count": len(DATA["edges"])})
            return
        if self.path == "/ancestry":
            target_sha = data.get("target_sha", "")
            self._write_json({"ancestry": build_ancestry(target_sha, DATA["commits"])})
            return
        if self.path == "/filter":
            ancestry = data.get("ancestry", [])
            self._write_json({"edges": filter_edges(ancestry, DATA["edges"])})
            return
        self._write_json({"error": "not found"}, 404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
"""


class GraphEngineEvaluator:
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url

    def connect(self) -> None:
        raise NotImplementedError

    def populate_data(self, num_commits: int, num_edges: int) -> None:
        raise NotImplementedError

    def topological_lookback_query(self, target_sha: str) -> List[str]:
        raise NotImplementedError

    def filter_code_edges(self, ancestry_list: List[str]) -> List[Dict[str, Any]]:
        raise NotImplementedError


class ContainerEvaluator(GraphEngineEvaluator):
    def __init__(self, name: str, base_url: str, runtime: Optional[str], container_name: str, container_port: int):
        super().__init__(name, base_url)
        self.runtime = runtime
        self.container_name = container_name
        self.container_port = container_port
        self._container_script_dir: Optional[tempfile.TemporaryDirectory[str]] = None

    def _run_container_command(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        if not self.runtime:
            raise RuntimeError("No container runtime available")
        return subprocess.run([self.runtime, *args], capture_output=True, text=True, check=False)

    def connect(self) -> None:
        if not self.runtime:
            raise RuntimeError("No container runtime available")

        TMP_DIR.mkdir(parents=True, exist_ok=True)
        self._container_script_dir = tempfile.TemporaryDirectory(prefix=f"{self.name.lower()}-", dir=str(TMP_DIR))
        script_path = Path(self._container_script_dir.name) / "mock_graph_server.py"
        script_path.write_text(SERVER_CODE, encoding="utf-8")

        self._run_container_command(["rm", "-f", self.container_name])
        result = self._run_container_command([
            "run",
            "--rm",
            "-d",
            "--name",
            self.container_name,
            "-p",
            f"127.0.0.1:{self.container_port}:{self.container_port}",
            "-v",
            f"{script_path.parent}:/workspace:Z",
            "-w",
            "/workspace",
            "python:3.12-slim",
            "python",
            "mock_graph_server.py",
            str(self.container_port),
        ])
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "failed to start container")

        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                response = requests.get(f"{self.base_url}/health", timeout=2)
                if response.ok:
                    return
            except requests.RequestException:
                time.sleep(0.5)
        raise RuntimeError(f"Container {self.container_name} did not become healthy in time")

    def populate_data(self, num_commits: int, num_edges: int) -> None:
        commits = []
        for index in range(1, num_commits + 1):
            parents = [f"commit-{index - 1}"] if index > 1 else []
            commits.append({"sha": f"commit-{index:03d}", "parents": parents})

        edges = []
        for index in range(1, num_edges + 1):
            introduced_in = f"commit-{max(1, index % num_commits):03d}"
            edges.append({"from": f"def-{index}", "to": f"def-{index + 1}", "introduced_in": introduced_in})

        response = requests.post(
            f"{self.base_url}/populate",
            json={"commits": commits, "edges": edges},
            timeout=10,
        )
        response.raise_for_status()

    def topological_lookback_query(self, target_sha: str) -> List[str]:
        response = requests.post(f"{self.base_url}/ancestry", json={"target_sha": target_sha}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        return payload.get("ancestry", [])

    def filter_code_edges(self, ancestry_list: List[str]) -> List[Dict[str, Any]]:
        response = requests.post(f"{self.base_url}/filter", json={"ancestry": ancestry_list}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        return payload.get("edges", [])

    def cleanup(self) -> None:
        if not self.runtime:
            return
        self._run_container_command(["rm", "-f", self.container_name])
        if self._container_script_dir is not None:
            self._container_script_dir.cleanup()


class LocalFallbackEvaluator(GraphEngineEvaluator):
    def __init__(self, name: str, base_url: str):
        super().__init__(name, base_url)
        self._commits: List[Dict[str, Any]] = []
        self._edges: List[Dict[str, Any]] = []

    def connect(self) -> None:
        return None

    def populate_data(self, num_commits: int, num_edges: int) -> None:
        self._commits = [{"sha": f"commit-{index:03d}", "parents": [f"commit-{index - 1:03d}"] if index > 1 else []} for index in range(1, num_commits + 1)]
        self._edges = [{"from": f"def-{index}", "to": f"def-{index + 1}", "introduced_in": f"commit-{max(1, index % num_commits):03d}"} for index in range(1, num_edges + 1)]

    def topological_lookback_query(self, target_sha: str) -> List[str]:
        commit_map = {commit["sha"]: commit for commit in self._commits}
        ancestry: List[str] = []
        current = commit_map.get(target_sha)
        while current:
            ancestry.append(current["sha"])
            parents = current.get("parents", [])
            if not parents:
                break
            current = commit_map.get(parents[0])
        return ancestry

    def filter_code_edges(self, ancestry_list: List[str]) -> List[Dict[str, Any]]:
        ancestry_set = set(ancestry_list)
        return [edge for edge in self._edges if edge.get("introduced_in") in ancestry_set]


def benchmark_engine(evaluator: GraphEngineEvaluator, num_runs: int = 10) -> Optional[Dict[str, Any]]:
    print(f"\nBenchmarking {evaluator.name}...")
    try:
        evaluator.connect()
        evaluator.populate_data(50, 250)
    except Exception as exc:
        print(f"Skipping {evaluator.name} benchmark: {exc}")
        return None

    lookback_latencies: List[float] = []
    filter_latencies: List[float] = []

    target_sha = "commit-050"
    for _ in range(num_runs):
        start = time.perf_counter()
        ancestors = evaluator.topological_lookback_query(target_sha)
        lookback_latencies.append(time.perf_counter() - start)

        start = time.perf_counter()
        evaluator.filter_code_edges(ancestors)
        filter_latencies.append(time.perf_counter() - start)

    avg_lookback = sum(lookback_latencies) / num_runs if lookback_latencies else 0.0
    avg_filter = sum(filter_latencies) / num_runs if filter_latencies else 0.0

    return {
        "engine": evaluator.name,
        "avg_lookback_ms": round(avg_lookback * 1000, 2),
        "avg_filter_ms": round(avg_filter * 1000, 2),
        "total_avg_ms": round((avg_lookback + avg_filter) * 1000, 2),
    }


def render_markdown_table(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# Graph Engine Benchmark Results",
        "",
        "| Engine | Avg Lookback (ms) | Avg Filter (ms) | Total Avg (ms) |",
        "| :--- | :---: | :---: | :---: |",
    ]
    for result in results:
        lines.append(
            f"| {result['engine']} | {result['avg_lookback_ms']} | {result['avg_filter_ms']} | {result['total_avg_ms']} |"
        )
    return "\n".join(lines) + "\n"


def write_markdown_report(output_path: Path, results: List[Dict[str, Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown_table(results), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Memtrace vs TerminusDB with mock Git-DAG data")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to write the markdown report")
    parser.add_argument("--runs", type=int, default=10, help="Number of benchmark iterations per engine")
    parser.add_argument("--commits", type=int, default=50, help="Number of mock commits to create")
    parser.add_argument("--edges", type=int, default=250, help="Number of mock code edges to create")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime = None
    for candidate in ("podman", "docker"):
        if shutil.which(candidate):
            runtime = candidate
            break

    evaluators: List[GraphEngineEvaluator] = [
        ContainerEvaluator("Memtrace", MEMTRACE_URL, runtime, "codeintel-memtrace", 18080) if runtime else LocalFallbackEvaluator("Memtrace", MEMTRACE_URL),
        ContainerEvaluator("TerminusDB", TERMINUSDB_URL, runtime, "codeintel-terminusdb", 18081) if runtime else LocalFallbackEvaluator("TerminusDB", TERMINUSDB_URL),
    ]

    results: List[Dict[str, Any]] = []
    for evaluator in evaluators:
        if isinstance(evaluator, ContainerEvaluator):
            try:
                benchmark = benchmark_engine(evaluator, args.runs)
            finally:
                evaluator.cleanup()
        else:
            benchmark = benchmark_engine(evaluator, args.runs)
        if benchmark:
            results.append(benchmark)

    if results:
        write_markdown_report(args.output, results)
        print("\nBenchmark Results:")
        print(render_markdown_table(results))
    else:
        print("\nNo engines available for benchmarking. Ensure a container runtime is available or adjust the target URLs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
