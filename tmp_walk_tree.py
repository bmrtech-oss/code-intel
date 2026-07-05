from tree_sitter_language_pack import get_parser
from pathlib import Path

for lang, path in [("python", "tests/golden/python/api.py"), ("typescript", "tests/golden/ts/repository.ts"), ("go", "tests/golden/go/main.go")]:
    parser = get_parser(lang)
    src = Path(path).read_text(encoding="utf-8")
    root = parser.parse(src).root_node()
    print("LANG", lang)
    def walk(node, depth=0):
        if depth > 5:
            return
        kind = node.kind() if callable(getattr(node, "kind", None)) else node.kind
        print("  " * depth + kind + f" ({node.child_count()})")
        for i in range(node.child_count()):
            walk(node.child(i), depth + 1)
    walk(root)
    print("---")
