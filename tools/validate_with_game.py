"""Compare the calculator with the game's own numbers.

Runs the game's data dump (`EndlessSky -s --loaded`), which prints stats for every ship model with its
stock outfits installed, and compares each column with the calculator. Needs a built game executable:

    python tools/validate_with_game.py path/to/EndlessSky path/to/endless-sky
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from es_optimizer import calculator, gamedata  # noqa: E402


def game_table(executable: str, resources: str) -> list[dict[str, str]]:
    out = subprocess.run([executable, "--resources", resources, "-s", "--loaded"],
                         capture_output=True, text=True, timeout=600, check=True).stdout
    start = out.index("model,")
    return list(csv.DictReader(io.StringIO(out[start:])))


def ours(ship: calculator.Ship) -> dict[str, float]:
    """The dump's columns, computed the way PrintData.cpp computes them."""
    g = ship.get
    energy = (g("energy consumption") + max(g("thrusting energy"), g("reverse thrusting energy"))
              + g("turning energy") + g("afterburner energy") + g("fuel energy")
              + g("hull energy") * (1 + g("hull energy multiplier"))
              + g("shield energy") * (1 + g("shield energy multiplier"))
              + g("cooling energy") + g("cloaking energy") + sum(w.energy for w in ship.weapons))
    heat = (g("heat generation") - g("cooling") + max(g("thrusting heat"), g("reverse thrusting heat"))
            + g("turning heat") + g("afterburner heat") + g("fuel heat")
            + g("hull heat") * (1 + g("hull heat multiplier"))
            + g("shield heat") * (1 + g("shield heat multiplier"))
            + g("solar heat") + g("cloaking heat") + sum(w.heat for w in ship.weapons))
    return {
        "cost": ship.cost,
        "shields": ship.max_shields,
        "hull": ship.max_hull,
        "mass": ship.mass,
        "fuel": g("fuel capacity"),
        "speed": 60 * g("thrust") / g("drag") if g("drag") else 0.0,
        "accel": 3600 * g("thrust") / ship.mass if ship.mass else 0.0,
        "turn": 60 * g("turn") / ship.mass if ship.mass else 0.0,
        "energy generation": 60 * (g("energy generation") + g("solar collection")),
        "max energy usage": 60 * energy,
        "energy capacity": g("energy capacity"),
        "idle/max heat": ship.equilibrium_heat(ship.idle_heat) / max(1.0, ship.max_heat),
        "max heat generation": 60 * heat,
        "max heat dissipation": 60 * 0.001 * g("heat dissipation") * ship.max_heat,
    }


def main() -> int:
    executable, resources = sys.argv[1], sys.argv[2]
    game = gamedata.load(Path(resources))
    rows = game_table(executable, resources)
    mismatches: dict[str, list[str]] = {}
    compared = 0
    for row in rows:
        hull = game.hulls.get(row["model"])
        if hull is None:
            mismatches.setdefault("missing model", []).append(row["model"])
            continue
        compared += 1
        mine = ours(calculator.build(game, hull, hull.stock_outfits))
        for column, value in mine.items():
            theirs = float(row[column])
            if abs(value - theirs) > 1e-3 * max(1.0, abs(theirs)):
                mismatches.setdefault(column, []).append(f"{row['model']}: ours {value:.6g}, game {theirs:.6g}")
    print(f"Compared {compared} ship models, {len(mine)} columns each.")
    if not mismatches:
        print("All values match the game.")
        return 0
    for column, items in mismatches.items():
        print(f"\n{column}: {len(items)} mismatches")
        for item in items[:8]:
            print("  " + item)
    return 1


if __name__ == "__main__":
    sys.exit(main())
