from tree_sitter_language_pack import get_parser
from pathlib import Path

for lang, path in [("python", "tests/golden/python/api.py"), ("typescript", "tests/golden/ts/repository.ts"), ("go", "tests/golden/go/main.go")]:
    parser = get_parser(lang)
    root = parser.parse(Path(path).read_text(encoding="utf-8")).root_node()
    print("LANG", lang)

    def walk(node):
        kind = node.kind() if callable(getattr(node, "kind", None)) else node.kind
        if kind in {"class_definition", "function_definition", "type_spec", "method_declaration", "class_declaration", "function_declaration", "call_expression", "call", "identifier", "type_identifier", "property_identifier", "field_identifier", "package_identifier"}:
            print("NODE", kind, "child_count", node.child_count())
            try:
                name_node = node.child_by_field_name("name")
                print("  child_by_field_name(name)", name_node, getattr(name_node, "kind", None), getattr(name_node, "text", None))
            except Exception as exc:
                print("  child_by_field_name(name) err", exc)
            for i in range(node.child_count()):
                child = node.child(i)
                ckind = child.kind() if callable(getattr(child, "kind", None)) else child.kind
                print("  child", i, ckind, "text", getattr(child, "text", None), "repr", child)
            print()
        for i in range(node.child_count()):
            walk(node.child(i))

    walk(root)
    print("---")
