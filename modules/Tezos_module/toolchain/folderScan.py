from pathlib import Path

SKIP_DIRS = {"__pycache__", "Library"}


def normalizeRoot(path):
    return Path(path).expanduser().resolve()


def folderScan(path, suite=None, include_scenarios=False):
    base_path = normalizeRoot(path)

    if base_path.name == "scenarios":
        return sorted(
            entry.stem
            for entry in base_path.iterdir()
            if entry.is_file() and entry.suffix == ".py" and not entry.name.startswith('.')
        )

    if base_path.name != "contracts":
        return sorted(
            entry.name
            for entry in base_path.iterdir()
            if entry.is_file() and not entry.name.startswith('.')
        )

    targets = set()
    normalized_suite = suite.lower() if suite else None

    for py_file in base_path.rglob("*.py"):
        relative_parent = py_file.parent.relative_to(base_path)
        parts = relative_parent.parts

        if not parts:
            continue

        if any(part.startswith('.') or part in SKIP_DIRS for part in parts):
            continue

        if not include_scenarios and "scenarios" in parts:
            continue

        if normalized_suite and parts[0].lower() != normalized_suite:
            continue

        if parts[0] in {"Legacy", "Rosetta"} and len(parts) >= 2:
            contract_folder = Path(*parts[:2]).as_posix()
        else:
            contract_folder = relative_parent.as_posix()

        targets.add(f"{contract_folder}:{py_file.stem}")

    return sorted(targets)


def scenarioScan(path):
    return folderScan(path)


def contractSuites(path):
    base_path = normalizeRoot(path)

    if base_path.name != "contracts" or not base_path.exists():
        return []

    suites = []
    for entry in sorted(base_path.iterdir()):
        if entry.is_dir() and not entry.name.startswith('.') and entry.name not in SKIP_DIRS:
            suites.append(entry.name)

    return suites
