import os
import sys
import importlib

def verify():
    print("--- Package Structure Verification ---")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = os.path.join(base_dir, "code_intel")

    # Dirs that MUST have __init__.py
    required_pkgs = [
        "code_intel",
        "code_intel/api",
        "code_intel/utils",
        "code_intel/core",
        "code_intel/mcp",
        "code_intel/cli",
        "code_intel/analytics",
        "code_intel/storage",
        "code_intel/semantic",
        "code_intel/lang",
        "code_intel/worker",
        "code_intel/cache"
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
    # Add code_intel to path just in case we are running outside uv/venv
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    modules_to_test = [
        "code_intel",
        "code_intel.cli.main",
        "code_intel.api.server",
        "code_intel.core.storage",
        "code_intel.core.ingestion"
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
