import subprocess
import os
from typing import List, Dict, Any

class GitService:
    def get_commit_timeline(self, repo_path: str) -> List[Dict[str, Any]]:
        """
        Use GitPython or subprocess to run: git log --format="%H|%ct" --reverse
        Return list of {"sha": str, "timestamp": int}
        """
        if not repo_path:
            return []

        # If it's not absolute and doesn't exist directly, resolve against current directory
        resolved_path = os.path.abspath(repo_path)
        if not os.path.exists(resolved_path):
            # Try to resolve path under CWD
            resolved_path = os.path.join(os.getcwd(), repo_path)
            if not os.path.exists(resolved_path):
                # Fallback to CWD just in case, or return empty list
                resolved_path = os.getcwd()

        try:
            result = subprocess.run(
                ["git", "log", "--format=%H|%ct", "--reverse"],
                cwd=resolved_path,
                capture_output=True,
                text=True,
                check=True
            )
            commits = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if "|" in line:
                    sha, timestamp_str = line.split("|", 1)
                    commits.append({
                        "sha": sha.strip(),
                        "timestamp": int(timestamp_str.strip())
                    })
            return commits
        except Exception as e:
            # Fail gracefully, maybe return a fallback or log
            print(f"Error fetching git timeline for path '{resolved_path}': {e}")
            return []
