from tree_sitter_language_pack import get_parser
from pathlib import Path

for lang, path in [("python", "tests/golden/python/api.py"), ("typescript", "tests/golden/ts/repository.ts"), ("go", "tests/golden/go/main.go")]:
    parser = get_parser(lang)
    code_intel = Path(path).read_text(encoding="utf-8")
    root = parser.parse(code_intel).root_node()
    print(lang, type(root))
    print("has type", hasattr(root, "type"))
    print("has kind", hasattr(root, "kind"))
    print("has text", hasattr(root, "text"))
    print("child_count", getattr(root, "child_count", None))
    print("children", getattr(root, "children", None))
    print("named_children", getattr(root, "named_children", None))
    print("child_by_field_name", getattr(root, "child_by_field_name", None))
    print("start_point", getattr(root, "start_point", None))
    print("end_point", getattr(root, "end_point", None))
    print("repr", root)
    print("---")
