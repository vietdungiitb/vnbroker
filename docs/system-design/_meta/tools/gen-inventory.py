#!/usr/bin/env python3
"""
gen-inventory.py — Sinh báo cáo số liệu từ codebase vnbroker.

Usage:
    python docs/system-design/_meta/tools/gen_inventory.py
    python docs/system-design/_meta/tools/gen_inventory.py --check

Output:
    docs/system-design/_meta/inventory.json
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def count_lines(file_path: Path) -> int:
    """Count lines in a file (matches wc -l)."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def count_files(pattern: str, root: Path) -> int:
    """Count files matching pattern."""
    return len(list(root.rglob(pattern)))


def get_git_info() -> Dict[str, str]:
    """Get git information."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent.parent.parent.parent.parent
        ).decode().strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=Path(__file__).parent.parent.parent.parent.parent
        ).decode().strip()
        return {"commit": commit, "branch": branch}
    except Exception:
        return {"commit": "unknown", "branch": "unknown"}


def generate_inventory() -> Dict[str, Any]:
    """Generate inventory report."""
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    vnbroker_dir = repo_root / "vnbroker"
    
    # Count Python files
    py_files = list(vnbroker_dir.rglob("*.py"))
    total_lines = sum(count_lines(f) for f in py_files)
    
    # Count by module
    modules = {}
    for py_file in py_files:
        rel_path = py_file.relative_to(vnbroker_dir)
        parts = rel_path.parts
        if len(parts) >= 2:
            module = parts[0]
            if module not in modules:
                modules[module] = {"files": 0, "lines": 0}
            modules[module]["files"] += 1
            modules[module]["lines"] += count_lines(py_file)
    
    # Count tests
    test_dir = repo_root / "tests"
    test_files = list(test_dir.rglob("test_*.py")) if test_dir.exists() else []
    test_lines = sum(count_lines(f) for f in test_files)
    
    # Count docs
    docs_dir = repo_root / "docs"
    doc_files = list(docs_dir.rglob("*.md")) if docs_dir.exists() else []
    
    # Git info
    git_info = get_git_info()
    
    return {
        "generated_at": subprocess.check_output(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], cwd=repo_root
        ).decode().strip(),
        "git": git_info,
        "codebase": {
            "total_py_files": len(py_files),
            "total_lines": total_lines,
            "modules": modules,
        },
        "tests": {
            "total_test_files": len(test_files),
            "total_test_lines": test_lines,
        },
        "docs": {
            "total_doc_files": len(doc_files),
        },
    }


def check_inventory(inventory_path: Path) -> bool:
    """Check if inventory is up to date."""
    if not inventory_path.exists():
        print("ERROR: inventory.json not found")
        return False
    
    with open(inventory_path, "r") as f:
        old = json.load(f)
    
    new = generate_inventory()
    
    # Compare key metrics
    old_total = old.get("codebase", {}).get("total_lines", 0)
    new_total = new.get("codebase", {}).get("total_lines", 0)
    
    if old_total != new_total:
        print(f"STALE: total_lines changed {old_total} -> {new_total}")
        return False
    
    print("OK: inventory is up to date")
    return True


def main():
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    inventory_path = repo_root / "docs" / "system-design" / "_meta" / "inventory.json"
    
    if "--check" in sys.argv:
        sys.exit(0 if check_inventory(inventory_path) else 1)
    
    inventory = generate_inventory()
    
    with open(inventory_path, "w") as f:
        json.dump(inventory, f, indent=2)
    
    print(f"Generated: {inventory_path}")
    print(f"Total lines: {inventory['codebase']['total_lines']}")
    print(f"Total files: {inventory['codebase']['total_py_files']}")


if __name__ == "__main__":
    main()
