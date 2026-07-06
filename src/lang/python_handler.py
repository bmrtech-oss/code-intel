from tree_sitter_language_pack import get_parser
from ..core.storage import VersionedStorage
import os

class PythonVisitor:
    def __init__(self, storage: VersionedStorage, file_path: str, version: str):
        self.storage = storage
        self.file_path = file_path
        self.version = version
        self.current_scope = []
        self.source_text = ""
        # Basic module name from file path
        module_name = os.path.splitext(file_path)[0].replace("\\", ".").replace("/", ".")
        if module_name.startswith("src."):
            module_name = module_name[4:]
        self.module_name = module_name

    async def parse(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.source_text = src
        parser = get_parser("python")
        tree = parser.parse(src)
        root = tree.root_node() if callable(getattr(tree, "root_node", None)) else tree.root_node
        await self._visit(root)

    def _get_fqn(self, name: str) -> str:
        if not self.current_scope:
            return f"{self.module_name}.{name}"
        return f"{self.module_name}.{'.'.join(self.current_scope)}.{name}"

    async def _visit(self, node):
        kind = self._node_kind(node)
        if kind == "class_definition":
            name_node = node.child_by_field_name("name") or self._find_child_by_kind(node, "identifier")
            if name_node:
                name = self._node_text(name_node)
                fqn = self._get_fqn(name)
                line = self._node_line(name_node)
                await self.storage.insert_symbol(self.file_path, fqn, "class", line, self.version)

                self.current_scope.append(name)
                for child in self._iter_children(node):
                    await self._visit(child)
                self.current_scope.pop()
                return

        elif kind == "function_definition":
            name_node = node.child_by_field_name("name") or self._find_child_by_kind(node, "identifier")
            if name_node:
                name = self._node_text(name_node)
                fqn = self._get_fqn(name)
                line = self._node_line(name_node)
                kind_name = "method" if self.current_scope else "function"
                await self.storage.insert_symbol(self.file_path, fqn, kind_name, line, self.version)

                self.current_scope.append(name)
                for child in self._iter_children(node):
                    await self._visit(child)
                self.current_scope.pop()
                return

        elif kind == "call":
            function_node = node.child_by_field_name("function")
            if function_node:
                callee = self._node_text(function_node)
                caller = ".".join([self.module_name] + self.current_scope)
                await self.storage.insert_call(caller, callee, 1.0, self.version)

                if self._node_kind(function_node) == "attribute":
                    await self.storage.insert_fact("dynamic_call", f"{caller}->{callee}", "type", "cross-file-candidate", self.version)

        for child in self._iter_children(node):
            await self._visit(child)

    def _iter_children(self, node):
        for i in range(node.child_count()):
            yield node.child(i)

    def _find_child_by_kind(self, node, kind):
        for child in self._iter_children(node):
            child_kind = self._node_kind(child)
            if child_kind == kind:
                return child
        return None

    def _node_text(self, node):
        start_byte = self._node_value(node, "start_byte")
        end_byte = self._node_value(node, "end_byte")
        if start_byte is None or end_byte is None:
            return ""
        return self.source_text[start_byte:end_byte]

    def _node_kind(self, node):
        return self._node_value(node, "kind")

    def _node_line(self, node):
        start_point = self._node_value(node, "start_point")
        if start_point is None:
            return 1
        if isinstance(start_point, (list, tuple)) and len(start_point) >= 1:
            return start_point[0] + 1
        return 1

    def _node_value(self, node, attr):
        value = getattr(node, attr, None)
        if callable(value):
            try:
                return value()
            except TypeError:
                return None
        return value
