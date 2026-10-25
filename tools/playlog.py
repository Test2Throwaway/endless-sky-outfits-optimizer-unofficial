"""Summarize play sessions recorded with the monitoring build (tools/warzone/play.sh).

    python tools/playlog.py ~/es-observe/logs/*.jsonl --resources ~/es-observe/src

For your fleet's fights (fleet against fleet, as in tools/warzone.py): per ship model, time in fight, gun /
turret / secondary duty, ammo used per fight, lowest energy, heat peak and how fights ended; plus the fleet
orders you gave. Writes experiments/play/summary.md and summary.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warzone  # noqa: E402

OUT = warzone.ROOT / "experiments" / "play"
ORDER_NAMES = ["hold position", "hold active", "move to", "keep station", "gather", "attack", "finish off",
               "hold fire", "mine", "harvest", "scan"]


def segments(path: Path):
    """Split a session into stretches in one system with a running frame counter (a load or a jump starts a new
    one). Yields (system, rows) where rows are the ship lines of that stretch."""
    current, system, last = [], None, -1
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "frame" in row:
                if row["system"] != system or row["frame"] < last:
                    if current:
                        yield system, current
                    current, system = [], row["system"]
                last = row["frame"]
            elif "id" in row:
                current.append(row)
    if current:
        yield system, current


def orders(path: Path) -> list[dict]:
    out = []
    with path.open() as f:
        for line in f:
            if line.startswith('{"order"'):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("logs", nargs="+")
    parser.add_argument("--resources", help="game folder, for weapon reload times and gun/turret kinds")
    args = parser.parse_args(argv)
    weapons = warzone.weapon_kinds(Path(args.resources) if args.resources else None)
    mine, given = [], []
    for name in args.logs:
        path = Path(name)
        given += orders(path)
        for system, rows in segments(path):
            ships = defaultdict(list)
            for r in rows:
                ships[r["id"]].append(r)
            for fight in warzone.analyse_run(system, ships, weapons):
                # Your fleet's fights: the fleet's ships are yours.
                own = [s for s in fight["ships"] if s.get("yours")]
                if own:
                    mine.append(dict(fight, ships=own))
    rows = [s for f in mine for s in f["ships"]]
    summary = {"fights": len(mine), "ship_records": len(rows),
               "fights_by_system": warzone.fleet_rows(mine, lambda f: f["system"]),
               "ships_by_model": warzone.ship_groups(rows, "model"),
               "orders": dict(Counter(ORDER_NAMES[o["order"]] if 0 <= o["order"] < len(ORDER_NAMES) else str(o["order"])
                                      for o in given))}
    lines = ["# Your fleet in play", "", f"{len(mine)} fleet fights, {len(rows)} ship records.", "",
             "## Fights by system", "", warzone.FLEET_HEAD, "|" + "---|" * 9]
    lines += [warzone.fleet_line(k, v) for k, v in summary["fights_by_system"].items()]
    lines += ["", "## Your ships, by model", "", warzone.SHIP_HEAD, "|" + "---|" * 14]
    lines += [warzone.ship_line(k, v) for k, v in summary["ships_by_model"].items()]
    lines += ["", "## Fleet orders given", ""] + [f"- {k}: {v}" for k, v in sorted(summary["orders"].items())]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
