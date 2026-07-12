import os
import sys
import importlib

def verify():
    print("--- Package Structure Verification ---")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "src")

    # Dirs that MUST have __init__.py
    required_pkgs = [
        "src",
        "src/api",
        "src/utils",
        "src/core",
        "src/mcp",
        "src/cli",
        "src/analytics",
        "src/storage",
        "src/semantic",
        "src/lang",
        "src/worker",
        "src/cache"
    ]

    all_passed = True
    for pkg in required_pkgs:
        init_file = os.path.join(base_dir, pkg, "__init__.py")
        if os.path.exists(init_file):
            print(f"✅ {pkg}/__init__.py exists")
        else:
            print(f"❌ {pkg}/__init__.py MISSING")
            all_passed = False

    print("\n--- Import Verification ---")
    # Add src to path just in case we are running outside uv/venv
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    modules_to_test = [
        "src",
        "src.cli.main",
        "src.api.server",
        "src.core.storage",
        "src.core.ingestion"
    ]

    for mod_name in modules_to_test:
        try:
            importlib.import_module(mod_name)
            print(f"✅ Imported {mod_name}")
        except ImportError as e:
            print(f"❌ Failed to import {mod_name}: {e}")
            all_passed = False

    if not all_passed:
        sys.exit(1)
    print("\nVerification successful!")

if __name__ == "__main__":
    verify()
