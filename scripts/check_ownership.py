#!/usr/bin/env python
"""
Ownership and dependency verification script.
Checks git changed files against OWNER or scans imports to enforce architecture boundaries.
"""

import os
import re
import sys
import subprocess

ALLOWED_PATHS = {
    "agent": ["agent/"],
    "integrations": ["integrations/"],
    "platform": [
        "server/",
        "e2e/",
        "scripts/",
        "docs/",
        "pyproject.toml",
        "Makefile",
        "README.md",
        ".env.example",
        "CODEOWNERS",
        ".gitignore",
        ".gitattributes"
    ]
}

def check_file_ownership(owner: str) -> bool:
    if owner not in ALLOWED_PATHS:
        print(f"Unknown owner: {owner}. Allowed: {list(ALLOWED_PATHS.keys())}")
        return False

    allowed_prefixes = ALLOWED_PATHS[owner]
    try:
        # Check files changed vs origin/main or HEAD~1
        res = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            res = subprocess.run(["git", "diff", "--name-only", "HEAD~1"], capture_output=True, text=True)
        changed_files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
    except Exception as e:
        print(f"Git diff failed: {e}. Skipping git check.")
        changed_files = []

    violations = []
    for f in changed_files:
        f_norm = f.replace("\\", "/")
        if not any(f_norm.startswith(p) or f_norm == p for p in allowed_prefixes):
            violations.append(f)

    if violations:
        print(f"ERROR: Owner '{owner}' modified files outside their assigned directories:")
        for v in violations:
            print(f"  - {v}")
        return False
    return True

def check_import_boundaries() -> bool:
    success = True
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    agent_dir = os.path.join(base_dir, "agent")
    if os.path.exists(agent_dir):
        for root, _, files in os.walk(agent_dir):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if re.search(r"^\s*(from|import)\s+(integrations|server)\b", content, re.MULTILINE):
                            print(f"ERROR: agent file {path} illegally imports integrations or server")
                            success = False

    integrations_dir = os.path.join(base_dir, "integrations")
    if os.path.exists(integrations_dir):
        for root, _, files in os.walk(integrations_dir):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if re.search(r"^\s*(from|import)\s+server\b", line):
                                print(f"ERROR: integrations file {path} illegally imports server")
                                success = False
                            # Integrations may only import agent.ports and agent.domain.enums
                            m = re.search(r"^\s*from\s+agent\.(\S+)\s+import", line)
                            if m:
                                mod = m.group(1)
                                if mod not in ("ports", "domain.enums"):
                                    print(f"ERROR: integrations file {path} illegally imports agent.{mod}")
                                    success = False

    return success

def main():
    owner = os.environ.get("OWNER", "platform").lower()
    print(f"Checking ownership for OWNER={owner}...")
    git_ok = check_file_ownership(owner)
    import_ok = check_import_boundaries()

    if not (git_ok and import_ok):
        print("Ownership and boundary check FAILED.")
        sys.exit(1)
    print("Ownership and boundary check PASSED.")

if __name__ == "__main__":
    main()

