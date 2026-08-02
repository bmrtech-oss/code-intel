from tree_sitter_language_pack import get_parser
from ..core.storage import VersionedStorage
import os

class PythonVisitor:
    def __init__(self, storage: VersionedStorage, file_path: str, version: str, root_path: str = None):
        self.storage = storage
        self.file_path = file_path
        self.version = version
        self.current_scope = []
        self.source_text = ""
        self.imports_map = {}
        self.root_path = root_path
        # Compute relative path from the repository root
        if root_path:
            rel_path = os.path.relpath(os.path.abspath(file_path), os.path.abspath(root_path))
        else:
            # Fallback relative to current working directory
            rel_path = os.path.relpath(file_path, os.getcwd())

        # Normalize separators and strip extension
        module_name = os.path.splitext(rel_path)[0].replace('\\\\', ".").replace("/", ".")
        module_name = module_name.lstrip(".")

        # Strip common source prefixes to align with Python import paths (e.g. "src.")
        if module_name.startswith("src."):
            module_name = module_name[4:]
        elif module_name.startswith("source."):
            module_name = module_name[7:]

        if module_name.startswith("code_intel."):
            module_name = module_name[4:]
        self.module_name = module_name

    async def parse(self):
        # Register the module itself as a symbol
        await self.storage.insert_symbol(self.file_path, self.module_name, "module", 1, self.version)

        with open(self.file_path, "r", encoding="utf-8") as f:
            code_intel = f.read()
        self.source_text = code_intel
        parser = get_parser("python")
        tree = self._parse_source(parser, code_intel)
        root = tree.root_node() if callable(getattr(tree, "root_node", None)) else tree.root_node
        await self._visit(root)

    def _parse_source(self, parser, code_intel: str):
        try:
            return parser.parse(code_intel)
        except TypeError:
            pass
        try:
            return parser.parse(code_intel.encode("utf-8"))
        except TypeError:
            source_bytes = code_intel.encode("utf-8")
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
                # Resolve local imported prefix using imports_map
                if "." in callee:
                    parts = callee.split(".")
                    first_part = parts[0]
                    if first_part in self.imports_map:
                        callee = self.imports_map[first_part] + "." + ".".join(parts[1:])
                elif callee in self.imports_map:
                    callee = self.imports_map[callee]
                caller = ".".join([self.module_name] + self.current_scope)

                confidence = 1.0
                fn_kind = self._node_kind(function_node)

                # Heuristic: attribute access is likely polymorphic or cross-file
                if fn_kind == "attribute":
                    confidence = 0.5
                # Dynamic reflection calls
                elif callee in ("getattr", "setattr", "hasattr", "__import__", "exec", "eval"):
                    confidence = 0.3

                await self.storage.insert_call(caller, callee, confidence, self.version)

                if fn_kind == "attribute":
                    await self.storage.insert_fact("dynamic_call", f"{caller}->{callee}", "type", "cross-file-candidate", self.version)

        elif kind == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module_name = self._node_text(module_node)
                # If it's not a local import, it's a cross-repo candidate
                # This is a simplification; normally we'd check if module_name is in our indexed set
                caller = ".".join([self.module_name] + self.current_scope)
                await self.storage.insert_cross_repo_import(caller, module_name, self.version)

                # Resolve imports in the workspace
                if self.root_path:
                    # 1. Detect Nested src/ Root
                    from pathlib import Path
                    root_path = Path(self.root_path)
                    search_roots = [root_path]
                    src_folder = root_path / "src"
                    if src_folder.exists() and src_folder.is_dir():
                        search_roots.append(src_folder)

                    # 2. Extract imported names
                    node_text = self._node_text(node)
                    imported_names = []
                    if "import " in node_text:
                        parts = node_text.split("import ")
                        if len(parts) > 1:
                            imports_part = parts[1]
                            raw_imports = [imp.strip().split(" as ")[0].strip('() \n\r\t') for imp in imports_part.split(",")]
                            imported_names = [imp for imp in raw_imports if imp]

                    # 3. Try resolving the base module or each imported specifier
                    resolved_specs = []
                    resolved_specs.append((module_name, module_name))
                    for name in imported_names:
                        full_spec = f"{module_name}.{name}"
                        resolved_specs.append((full_spec, name))

                    for spec, name in resolved_specs:
                        rel_path_str = spec.replace(".", "/")
                        resolved_file = None
                        for s_root in search_roots:
                            py_file = s_root / f"{rel_path_str}.py"
                            if py_file.exists() and py_file.is_file():
                                resolved_file = str(py_file.resolve())
                                break
                            init_file = s_root / rel_path_str / "__init__.py"
                            if init_file.exists() and init_file.is_file():
                                resolved_file = str(init_file.resolve())
                                break

                        if resolved_file:
                            # We resolved a workspace module to a physical file!
                            # Insert a CALL edge representing the module import dependency!
                            await self.storage.insert_call(self.module_name, spec, 1.0, self.version)

        elif kind == "import_statement":
            # Example: "import app.api"
            node_text = self._node_text(node)
            if "import " in node_text:
                parts = node_text.split("import ")
                if len(parts) > 1:
                    imports_part = parts[1]
                    raw_imports = [imp.strip().split(" as ")[0].strip('() \n\r\t') for imp in imports_part.split(",")]
                    imported_names = [imp for imp in raw_imports if imp]

                    if self.root_path:
                        from pathlib import Path
                        root_path = Path(self.root_path)
                        search_roots = [root_path]
                        src_folder = root_path / "src"
                        if src_folder.exists() and src_folder.is_dir():
                            search_roots.append(src_folder)

                        for spec in imported_names:
                            # Populate imports_map
                            self.imports_map[spec] = spec
                            if "." in spec:
                                last_name = spec.split(".")[-1]
                                self.imports_map[last_name] = spec

                            rel_path_str = spec.replace(".", "/")
                            resolved_file = None
                            for s_root in search_roots:
                                py_file = s_root / f"{rel_path_str}.py"
                                if py_file.exists() and py_file.is_file():
                                    resolved_file = str(py_file.resolve())
                                    break
                                init_file = s_root / rel_path_str / "__init__.py"
                                if init_file.exists() and init_file.is_file():
                                    resolved_file = str(init_file.resolve())
                                    break

                            if resolved_file:
                                await self.storage.insert_call(self.module_name, spec, 1.0, self.version)

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
