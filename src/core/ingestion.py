import os
from .storage import VersionedStorage
from ..lang.python_handler import PythonVisitor
from ..lang.java_handler import JavaVisitor
from ..lang.cobol_handler import CobolVisitor      # now available via pack
from ..lang.delphi_handler import DelphiVisitor

class IngestionPipeline:
    def __init__(self, storage: VersionedStorage):
        self.storage = storage

    async def walk_and_parse(self, root_path: str, version: str):
        for dirpath, _, filenames in os.walk(root_path):
            for fname in filenames:
                full_path = os.path.join(dirpath, fname)
                await self.parse_file(full_path, version)

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
        else:
            return  # skip unsupported files
        await visitor.parse()