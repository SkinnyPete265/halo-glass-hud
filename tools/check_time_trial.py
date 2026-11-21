"""Check Halo's split sequence in a saved UDP-off Time Trial loader log."""

import argparse
from pathlib import Path
import re

PREFIX = "[halo-v2-sectors] "
PROVIDER = re.compile(r"generation=(\d+) player=(\d+) provider=(.+)")
SPLIT = re.compile(r"accepted lap=(\d+) S([123])=(\d+) ms")


def complete_laps(log):
    context = None
    live = False
    segments = [{}]
    for line in log.splitlines():
        _, marker, event = line.partition(PREFIX)
        if not marker:
            continue
        selected = PROVIDER.fullmatch(event)
        if selected:
            current = selected.groups()[:2]
            if context is not None and current != context:
                segments.append({})
            context, live = current, selected[3] == "live.car_detail"
            continue
        if event.startswith("player lap counter or clock rewound"):
            segments.append({})
            continue
        split = SPLIT.fullmatch(event)
        if not split:
            continue
        if not live:
            raise ValueError("Accepted a split without the Live v6 provider")
        lap, sector, _ = map(int, split.groups())
        sectors = segments[-1].setdefault(lap, [])
        if sectors and sector <= sectors[-1]:
            raise ValueError(f"Duplicate or out-of-order S{sector} on lap {lap}")
        sectors.append(sector)
    return [sorted(lap for lap, sectors in segment.items() if sectors == [1, 2, 3])
            for segment in segments]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--restart", action="store_true", help="Require complete laps before and after a reset")
    args = parser.parse_args()
    try:
        laps = complete_laps(args.log.read_text(encoding="utf-8", errors="replace"))
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    if not any(laps) or (args.restart and sum(bool(segment) for segment in laps) < 2):
        parser.exit(1, "Missing all three Live v6 splits in the requested test segments.\n")
    print(f"Complete Live v6 laps by session or restart: {laps}")


if __name__ == "__main__":
    main()
