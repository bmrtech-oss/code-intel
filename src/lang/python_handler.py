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
        tree = self._parse_source(parser, src)
        root = tree.root_node() if callable(getattr(tree, "root_node", None)) else tree.root_node
        await self._visit(root)

    def _parse_source(self, parser, src: str):
        try:
            return parser.parse(src)
        except TypeError:
            pass
        try:
            return parser.parse(src.encode("utf-8"))
        except TypeError:
            source_bytes = src.encode("utf-8")
            return parser.parse(lambda start, end: source_bytes[start:end])

    def _get_fqn(self, name: str) -> str:
        if not self.current_scope:
            return f"{self.module_name}.{name}"
        return f"{self.module_name}.{'.'.join(self.current_scope)}.{name}"

    def _extract_docstring(self, node):
        body = node.child_by_field_name("body")
        if body:
            first_child = next(self._iter_children(body), None)
            if first_child and self._node_kind(first_child) == "expression_statement":
                expr = next(self._iter_children(first_child), None)
                if expr and self._node_kind(expr) == "string":
                    return self._node_text(expr).strip('\'" ')
        return None

    async def _visit(self, node):
        kind = self._node_kind(node)
        if kind == "class_definition":
            name_node = node.child_by_field_name("name") or self._find_child_by_kind(node, "identifier")
            if name_node:
                name = self._node_text(name_node)
                fqn = self._get_fqn(name)
                line = self._node_line(name_node)
                docstring = self._extract_docstring(node)

                await self.storage.insert_symbol(self.file_path, fqn, "class", line, self.version)
                if docstring:
                    await self.storage.insert_fact("symbol", f"class:{fqn}", "docstring", docstring, self.version)

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
                docstring = self._extract_docstring(node)

                # Extract signature (parameters)
                params_node = node.child_by_field_name("parameters")
                signature = self._node_text(params_node) if params_node else ""

                await self.storage.insert_symbol(self.file_path, fqn, kind_name, line, self.version)
                if docstring:
                    await self.storage.insert_fact("symbol", f"{kind_name}:{fqn}", "docstring", docstring, self.version)
                if signature:
                    await self.storage.insert_fact("symbol", f"{kind_name}:{fqn}", "signature", signature, self.version)

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

        elif kind == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module_name = self._node_text(module_node)
                # If it's not a local import, it's a cross-repo candidate
                # This is a simplification; normally we'd check if module_name is in our indexed set
                caller = ".".join([self.module_name] + self.current_scope)
                await self.storage.insert_fact("cross_repo_import", f"{caller}->{module_name}", "module", module_name, self.version)

        for child in self._iter_children(node):
            await self._visit(child)

    def _iter_children(self, node):
        child_count = getattr(node, "child_count", None)
        if callable(child_count):
            child_count = child_count()
        if child_count is None:
            child_count = len(getattr(node, "children", []) or [])
        if callable(getattr(node, "child", None)):
            for i in range(child_count or 0):
                yield node.child(i)
        else:
            for child in getattr(node, "children", []) or []:
                yield child

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
        candidates = [attr]
        if attr == "kind":
            candidates.append("type")
        elif attr == "type":
            candidates.append("kind")

        for candidate in candidates:
            value = getattr(node, candidate, None)
            if callable(value):
                try:
                    return value()
                except TypeError:
                    return None
            if value is not None:
                return value
        return None
