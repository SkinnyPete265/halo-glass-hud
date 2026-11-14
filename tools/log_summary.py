"""Compact diagnostics and warning differences from preserved raw build logs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def read_log(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return ANSI.sub("", raw.decode(encoding, errors="replace"))


def summarize(path, baseline=None, exit_code=0):
    lines = read_log(path).splitlines()
    warnings = []
    errors = []
    counts = Counter()
    for line in lines:
        lower = line.lower()
        if re.fullmatch(r"\s*\d+ errors?, \d+ warnings?\s*", lower):
            continue
        if "[catalogue]" in lower:
            category = "catalogue"
        elif "stock layout" in lower or "built into the game files;" in lower:
            category = "archive-layout"
        elif re.search(r"\bwarn(?:ing)?\b", lower):
            category = "other"
        else:
            category = None
        if category:
            counts[category] += 1
            warnings.append((category, line.strip()))
        if re.search(
            r"(?:^|\s)(?:error:|fatal:|[A-Za-z]+Error:|Traceback)", line, re.I
        ):
            errors.append(line.strip())
    previous = {}
    if baseline and baseline.exists():
        try:
            previous = json.loads(baseline.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
    previous_keys = set(previous.get("warning_keys", []))

    def key(item):
        normalized = re.sub(r"\b[0-9a-f]{16,64}\b", "<hash>", item[1])
        return hashlib.sha256((item[0] + " " + normalized).encode()).hexdigest()

    unique = {key(item): item for item in warnings}
    new = [
        {"category": item[0], "text": item[1][:500]}
        for identity, item in unique.items()
        if identity not in previous_keys
    ]
    return {
        "log": str(path),
        "exit_code": exit_code,
        "warning_counts": dict(counts),
        "new_warning_count": len(new),
        "new_warnings": new[:8],
        "errors": errors[-8:],
        "failure_tail": lines[-12:] if exit_code and not errors else [],
        "warning_keys": sorted(unique),
        "baseline": str(baseline) if baseline else None,
    }


def save_summary(path, baseline=None, exit_code=0, accept=False):
    result = summarize(path, baseline, exit_code)
    target = path.with_suffix(".summary.json")
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if accept and baseline and not exit_code:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        pending = baseline.with_suffix(".tmp")
        pending.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        pending.replace(baseline)
    compact = {key: value for key, value in result.items() if key != "warning_keys"}
    compact["report"] = str(target)
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    print(json.dumps(save_summary(args.log, args.baseline), indent=2))


if __name__ == "__main__":
    main()
