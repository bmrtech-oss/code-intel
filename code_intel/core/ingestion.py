import os
from .storage import VersionedStorage
from ..lang.python_handler import PythonVisitor
from ..lang.java_handler import JavaVisitor
from ..lang.cobol_handler import CobolVisitor      # now available via pack
from ..lang.delphi_handler import DelphiVisitor
from ..lang.cs_handler import CSharpVisitor

class IngestionPipeline:
    def __init__(self, storage: VersionedStorage):
        self.storage = storage

    async def walk_and_parse(self, root_path: str, version: str, job_id: str = None):
        all_files = []
        for dirpath, _, filenames in os.walk(root_path):
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in (".py", ".java", ".cob", ".cbl", ".cobol", ".pas", ".dpr", ".dpk", ".cs"):
                    all_files.append(os.path.join(dirpath, fname))

        total_files = len(all_files)
        parsed_count = 0

        for full_path in all_files:
            parsed_count += 1
            if job_id:
                try:
                    import json
                    from redis import Redis
                    redis_host = os.getenv("REDIS_HOST", "redis")
                    redis_port = int(os.getenv("REDIS_PORT", 6379))
                    r = Redis(host=redis_host, port=redis_port)

                    progress_percent = int((parsed_count / total_files) * 100) if total_files > 0 else 100
                    progress_data = {
                        "file": os.path.basename(full_path),
                        "progress": progress_percent,
                        "done": False,
                        "parsed_count": parsed_count,
                        "total_files": total_files
                    }
                    r.set(f"progress:{job_id}", json.dumps(progress_data))
                except Exception as e:
                    print(f"Error updating progress in Redis: {e}")

            await self.parse_file(full_path, version)

        if job_id:
            try:
                import json
                from redis import Redis
                redis_host = os.getenv("REDIS_HOST", "redis")
                redis_port = int(os.getenv("REDIS_PORT", 6379))
                r = Redis(host=redis_host, port=redis_port)

                progress_data = {
                    "file": "",
                    "progress": 100,
                    "done": True,
                    "parsed_count": parsed_count,
                    "total_files": total_files
                }
                r.set(f"progress:{job_id}", json.dumps(progress_data))
            except Exception as e:
                print(f"Error updating final progress in Redis: {e}")

    async def parse_file(self, file_path: str, version: str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".py":
            visitor = PythonVisitor(self.storage, file_path, version)
        elif ext == ".java":
            visitor = JavaVisitor(self.storage, file_path, version)
        elif ext in (".cob", ".cbl", ".cobol"):
            visitor = CobolVisitor(self.storage, file_path, version)
        elif ext in (".pas", ".dpr", ".dpk"):
            visitor = DelphiVisitor(self.storage, file_path, version)
        elif ext == ".cs":
            visitor = CSharpVisitor(self.storage, file_path, version)
        else:
            return  # skip unsupported files
        await visitor.parse()