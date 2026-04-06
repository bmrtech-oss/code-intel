import os
import tempfile
import shutil
from git import Repo, GitCommandError
from typing import Optional

class GitRepoHandler:
    def __init__(self, repo_url: str, branch: Optional[str] = None, depth: Optional[int] = None):
        self.repo_url = repo_url
        self.branch = branch
        self.depth = depth
        self.temp_dir = None
        self.repo = None

    def clone(self) -> str:
        self.temp_dir = tempfile.mkdtemp(prefix="codeintel_")
        try:
            # Build clone options
            clone_kwargs = {
                'url': self.repo_url,
                'to_path': self.temp_dir,
                'depth': self.depth,
            }
            if self.branch:
                clone_kwargs['branch'] = self.branch
            self.repo = Repo.clone_from(**clone_kwargs)
            return self.temp_dir
        except GitCommandError as e:
            # If branch not found, try cloning without branch (default branch)
            if self.branch and 'branch' in str(e).lower():
                try:
                    self.repo = Repo.clone_from(self.repo_url, self.temp_dir, depth=self.depth)
                    return self.temp_dir
                except Exception as fallback_error:
                    raise RuntimeError(f"Failed to clone repository (fallback): {fallback_error}")
            else:
                raise RuntimeError(f"Failed to clone repository: {e}")
        except Exception as e:
            self.cleanup()
            raise RuntimeError(f"Failed to clone repository: {e}")

    def cleanup(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None
            self.repo = None