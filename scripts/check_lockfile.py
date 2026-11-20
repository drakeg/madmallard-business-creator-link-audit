#!/usr/bin/env python3
"""Fail CI if a declared Python requirement disagrees with the pinned lockfile."""
from pathlib import Path
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]

def read_requirements(path):
    found = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            requirement = Requirement(line)
            found[requirement.name.lower()] = requirement
    return found

def inconsistencies(root=ROOT):
    declared = read_requirements(root / "requirements.txt")
    locked = read_requirements(root / "requirements.lock")
    errors = []
    for name, requirement in sorted(declared.items()):
        pin = locked.get(name)
        if pin is None:
            errors.append(f"{name}: missing from lockfile")
            continue
        exact = [spec for spec in pin.specifier if spec.operator == "=="]
        if len(exact) != 1 or not pin.specifier.contains(Version(exact[0].version)):
            errors.append(f"{name}: lock must have one exact version")
        elif Version(exact[0].version) not in requirement.specifier:
            errors.append(f"{name}: lock {exact[0].version} disagrees with {requirement.specifier}")
    return errors

if __name__ == "__main__":
    errors = inconsistencies()
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("Declared requirements match locked versions")
