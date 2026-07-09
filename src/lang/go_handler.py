from tree_sitter_language_pack import get_parser
from ..core.storage import VersionedStorage

class GoVisitor:
    def __init__(self, storage: VersionedStorage, file_path: str, version: str):
        self.storage = storage
        self.file_path = file_path
        self.version = version
        self.package_name = ""
        self.current_scope = []
        self.source_text = ""

    async def parse(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            src = f.read()
        self.source_text = src
        parser = get_parser("go")
        tree = self._parse_source(parser, src)
        root = tree.root_node() if callable(getattr(tree, "root_node", None)) else tree.root_node
        # First pass to find package name
        self._find_package(root)
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

    def _find_package(self, node):
        if self._node_kind(node) == "package_clause":
            for child in self._iter_children(node):
                if self._node_kind(child) == "package_identifier":
                    self.package_name = self._node_text(child)
                    return
        for child in self._iter_children(node):
            self._find_package(child)
            if self.package_name:
                break

    def _get_fqn(self, name: str) -> str:
        prefix = self.package_name
        if self.current_scope:
            prefix = f"{prefix}.{'.'.join(self.current_scope)}"
        return f"{prefix}.{name}"

    async def _visit(self, node):
        kind = self._node_kind(node)
        if kind == "type_spec":
            name_node = self._find_child_by_kind(node, "type_identifier") or self._find_child_by_kind(node, "identifier")
            if name_node:
                name = self._node_text(name_node)
                fqn = self._get_fqn(name)
                line = self._node_line(name_node)
                await self.storage.insert_symbol(self.file_path, fqn, "type", line, self.version)

        elif kind == "function_declaration":
            name_node = self._find_child_by_kind(node, "identifier")
            if name_node:
                name = self._node_text(name_node)
                fqn = self._get_fqn(name)
                line = self._node_line(name_node)
                await self.storage.insert_symbol(self.file_path, fqn, "function", line, self.version)

                self.current_scope.append(name)
                for child in self._iter_children(node):
                    await self._visit(child)
                self.current_scope.pop()
                return

        elif kind == "method_declaration":
            name_node = self._find_child_by_kind(node, "field_identifier") or self._find_child_by_kind(node, "identifier")
            receiver_node = node.child_by_field_name("receiver")
            receiver_type = ""
            if receiver_node:
                receiver_text = self._node_text(receiver_node)
                receiver_type = receiver_text.split()[-1].strip("*()")

            if name_node:
                name = self._node_text(name_node)
                fqn = f"{self.package_name}.{receiver_type}.{name}" if receiver_type else self._get_fqn(name)
                line = self._node_line(name_node)
                await self.storage.insert_symbol(self.file_path, fqn, "method", line, self.version)

                self.current_scope.append(f"{receiver_type}.{name}" if receiver_type else name)
                for child in self._iter_children(node):
                    await self._visit(child)
                self.current_scope.pop()
                return

        elif kind == "call_expression":
            function_node = node.child_by_field_name("function")
            if function_node:
                callee = self._node_text(function_node)
                caller = ".".join([self.package_name] + self.current_scope)
                await self.storage.insert_call(caller, callee, 1.0, self.version)

                if self._node_kind(function_node) == "selector_expression":
                    await self.storage.insert_fact("dynamic_call", f"{caller}->{callee}", "type", "cross-file-candidate", self.version)

        elif kind == "import_spec":
            path_node = node.child_by_field_name("path")
            if path_node:
                import_path = self._node_text(path_node).strip("'\"")
                # Cross-repo Go imports typically contain a dot (e.g., github.com/...)
                if "." in import_path:
                    caller = ".".join([self.package_name] + self.current_scope)
                    await self.storage.insert_fact("cross_repo_import", f"{caller}->{import_path}", "module", import_path, self.version)

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
