#!/usr/bin/env python3
"""Local, dependency-free checks for minimum Mad Mallard repository requirements."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("README.md", "AGENTS.md", "SPRINTS.md", "BACKLOG.md", "CONTRIBUTING.md", "RELEASES.md", "SECURITY.md")

def check(root=ROOT):
    errors = []
    for name in DOCUMENTS:
        if not (root / name).is_file():
            errors.append(f"Missing {name}")
    readme = (root / "README.md")
    if readme.exists():
        contents = readme.read_text()
        start, end = "<!-- madmallard-badges:start -->", "<!-- madmallard-badges:end -->"
        if contents.count(start) != 1 or contents.count(end) != 1:
            errors.append("Exactly one badge block is required")
        else:
            first_heading = re.search(r"(?m)^# .+$", contents)
            if not first_heading or contents.index(start) < first_heading.end() or contents[:contents.index(start)].count("\n") > 3:
                errors.append("Badges must appear immediately after README H1")
            badges = contents.split(start)[1].split(end)[0]
            if "/badge/build-passing" in badges or "/badge/tests-passing" in badges:
                errors.append("Static success badge detected")
            if "/actions/workflows/" not in badges:
                errors.append("Missing dynamic CI status badge")
    return errors

if __name__ == "__main__":
    result = check()
    if result:
        print("\n".join(result), file=sys.stderr)
        sys.exit(1)
    print("Repository standards: OK")
