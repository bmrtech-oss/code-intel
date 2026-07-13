from tree_sitter_language_pack import get_parser
from ..core.storage import VersionedStorage

class CSharpVisitor:
    def __init__(self, storage: VersionedStorage, file_path: str, version: str):
        self.storage = storage
        self.file_path = file_path
        self.version = version

    async def parse(self):
        with open(self.file_path, "rb") as f:
            code_intel = f.read()
        parser = get_parser("csharp")
        tree = parser.parse(code_intel)
        await self._visit(tree.root_node)

    async def _visit(self, node):
        if node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode('utf-8')
                line = name_node.start_point[0] + 1
                await self.storage.insert_symbol(self.file_path, name, "class", line, self.version)
        elif node.type == "method_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                name = name_node.text.decode('utf-8')
                line = name_node.start_point[0] + 1
                await self.storage.insert_symbol(self.file_path, name, "method", line, self.version)
        for child in node.children:
            await self._visit(child)
