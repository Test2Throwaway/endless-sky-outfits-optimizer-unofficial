"""Watch stock NPC fleets fight in war-zone systems, headless, and log every ship twice a second.

Needs an Endless Sky 0.11.2 build with tools/warzone/combat-log.patch applied (an out-of-tree copy;
the game repo itself is never touched), plus xvfb-run.

    python tools/warzone.py plugin --resources ES_SRC          # write the test plugin into the config template
    python tools/warzone.py run --game BUILD/endless-sky --resources ES_SRC [--minutes 20] [--repeats 1]
    python tools/warzone.py analyse                             # experiments/warzone/summary.json + .md

Each run starts the player landed in the system (or on a stand-in planet), then departs, in a weaponless ship with no cargo space and
friendly to every government, so the NPCs only fight each other. The patched game writes one JSON line per
ship every 30 frames (ES_COMBAT_LOG): energy, heat, shields, hull, fuel, ammo per ammo outfit, shots per
weapon since the last line, enemy target distance, and the disabled / destroyed / jumping / fleeing flags.

Results: experiments/warzone/logs/<system>-<n>.jsonl (gitignored, large), summary.json, summary.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "warzone"
LOGS = OUT / "logs"

# System → minutes multiplier. The Korath raid systems get 3× the time: raids come every 35,000–65,000 frames.
SYSTEMS = {
    "Nunki": 1, "Shaula": 1, "Lesath": 1, "Beta Lupi": 1, "Almaaz": 1,
    "Misam": 3, "Durax": 3, "Polaris": 3,
}
# The save must name a planet. Beta Lupi, Lesath and Durax have none, so the player "lands" on a stand-in; the
# engine then places the departing flagship in the save's system (its fallback for a planet not in the system).
PLANETS = {"Nunki": "Albatross", "Shaula": "Greenrock", "Almaaz": "Freedom", "Misam": "New Tortuga",
           "Polaris": "Shangri-La"}
STAND_IN_PLANET = "New Tortuga"
FRAMES_PER_STEP = 30  # one test "input" step
FPS = 60
SAMPLE_FRAMES = 30    # the patch logs every 30 frames

# A fight, for one ship: samples where it fired, or took damage, or had an enemy target within this range,
# merged across gaps shorter than FIGHT_GAP seconds.
ENGAGE_RANGE = 3000.
FIGHT_GAP = 10.
MIN_FIGHT = 5.
# A jump out below this health (shields + hull above the disable line, as a share of full) counts as a retreat;
# above it, the ship was most likely just travelling on.
RETREAT_HEALTH = 0.95


def governments(resources: Path) -> list[str]:
    names = set()
    for path in (resources / "data").rglob("*.txt"):
        for match in re.finditer(r'^government "?([^"\n]+?)"?\s*$', path.read_text(errors="ignore"), re.M):
            names.add(match.group(1))
    return sorted(names)


def quote(text: str) -> str:
    return f'"{text}"' if " " in text or not text else text


def test_name(system: str) -> str:
    return f"warzone {system}"


def plugin_text(resources: Path, minutes: float) -> str:
    reputation = "\n".join(f"\t\t\t{quote(g)} 1000" for g in governments(resources))
    parts = []
    for system, factor in SYSTEMS.items():
        steps = int(minutes * factor * 60 * FPS / FRAMES_PER_STEP)
        save = f"warzone {system} save"
        planet = quote(PLANETS.get(system, STAND_IN_PLANET))
        parts.append(f"""test-data "{save}"
\tcategory "savegame"
\tcontents
\t\tpilot War Watcher
\t\tdate 16 11 3013
\t\tsystem {quote(system)}
\t\tplanet {planet}
\t\tship "Star Barge"
\t\t\tname "Watcher"
\t\t\tsprite "ship/star barge"
\t\t\tattributes
\t\t\t\tcategory "Light Freighter"
\t\t\t\tmass 70
\t\t\t\tbunks 1
\t\t\t\tdrag 2.1
\t\t\t\t"engine capacity" 400
\t\t\t\t"fuel capacity" 300
\t\t\t\t"heat dissipation" 0.8
\t\t\t\thull 100000
\t\t\t\tshields 100000
\t\t\t\t"outfit space" 1300
\t\t\t\t"required crew" 1
\t\t\toutfits
\t\t\t\tHyperdrive
\t\t\t\t"X1700 Ion Thruster"
\t\t\t\t"X1200 Ion Steering"
\t\t\t\t"nGVF-BB Fuel Cell"
\t\t\t\t"LP036a Battery Pack"
\t\t\tcrew 1
\t\t\tfuel 300
\t\t\tshields 100000
\t\t\thull 100000
\t\t\tengine -9 38 1
\t\t\tengine 9 38 1
\t\t\tsystem {quote(system)}
\t\t\tplanet {planet}
\t\taccount
\t\t\tcredits 0
\t\t\tscore 0
\t\t\thistory
\t\t"reputation with"
{reputation}
\t\tvisited {quote(system)}

test "{test_name(system)}"
\tstatus active
\tdescription "Watch NPC fleets fight in {system} for {minutes * factor:g} game minutes."
\tsequence
\t\tinject "{save}"
\t\tcall "Load First Savegame"
\t\tcall "Depart"
\t\tinput
\t\tassert
\t\t\t"flagship landed" == 0
\t\tapply
\t\t\t"test: steps to wait" = {steps}
\t\tlabel "watching"
\t\tinput
\t\tapply
\t\t\t"test: steps to wait" = "test: steps to wait" - 1
\t\tbranch "watching"
\t\t\t"test: steps to wait" > 0
""")
    return "\n\n".join(parts)


def write_config(resources: Path, minutes: float, target: Path) -> None:
    """A config folder: the game's integration-test template (preferences and helper tests) plus our tests."""
    template = resources / "tests" / "integration" / "config"
    shutil.copytree(template, target, dirs_exist_ok=True)
    plugin = target / "plugins" / "warzone" / "data"
    plugin.mkdir(parents=True, exist_ok=True)
    (plugin / "warzone.txt").write_text(plugin_text(resources, minutes))


def cmd_plugin(args) -> None:
    target = Path(args.out)
    write_config(Path(args.resources), args.minutes, target)
    print(f"config with the warzone tests written to {target}")


def run_one(game: Path, resources: Path, minutes: float, system: str, log: Path) -> tuple[bool, float, str]:
    with tempfile.TemporaryDirectory() as config:
        write_config(resources, minutes, Path(config))
        partial = log.with_suffix(".partial")
        partial.unlink(missing_ok=True)
        env = dict(os.environ, ES_COMBAT_LOG=str(partial))
        start = time.time()
        proc = subprocess.run(
            ["xvfb-run", "--auto-servernum", "--server-args=+extension GLX +render -noreset",
             str(game), "--resources", str(resources), "--config", config, "--test", test_name(system)],
            env=env, capture_output=True, text=True)
        elapsed = time.time() - start
        errors = Path(config) / "errors.txt"
        detail = (errors.read_text()[-2000:] if errors.exists() else "") + proc.stderr[-2000:]
        ok = proc.returncode == 0 and partial.exists()
        if ok:
            partial.rename(log)
        return ok, elapsed, detail


def cmd_run(args) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    game, resources = Path(args.game).resolve(), Path(args.resources).resolve()
    systems = args.systems or list(SYSTEMS)
    todo = [(n, system) for n in range(args.repeats) for system in systems
            if not (LOGS / f"{system.replace(' ', '_')}-{n}.jsonl").exists()]

    def job(item):
        n, system = item
        log = LOGS / f"{system.replace(' ', '_')}-{n}.jsonl"
        ok, elapsed, detail = run_one(game, resources, args.minutes, system, log)
        print(f"{system} #{n} ({args.minutes * SYSTEMS[system]:g} game minutes): "
              f"{'done' if ok else 'FAILED'} in {elapsed:.0f} s", flush=True)
        if not ok:
            print(detail, flush=True)

    print(f"{len(todo)} runs to do", flush=True)
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        list(pool.map(job, todo))


# ---------------------------------------------------------------------------------------------------------
# Analysis

def load_samples(path: Path) -> dict[str, list[dict]]:
    ships = defaultdict(list)
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut off when the run ended
            ships[row["id"]].append(row)
    return ships


def fights(samples: list[dict]) -> list[tuple[int, int]]:
    """Index ranges [start, end] of this ship's fights. A fight ends at the first disabled or destroyed sample."""
    active = []
    for i, s in enumerate(samples):
        if s["disabled"] or s["destroyed"]:
            if active and i - active[-1] <= FIGHT_GAP * FPS / SAMPLE_FRAMES:
                active.append(i)
            break
        hit = i > 0 and (s["shields"] + s["hull"] < samples[i - 1]["shields"] + samples[i - 1]["hull"] - 1e-6)
        fired = any(s["shots"].values())
        near = 0 <= s["target"] <= ENGAGE_RANGE
        if hit or fired or near:
            active.append(i)
    gap = FIGHT_GAP * FPS / SAMPLE_FRAMES
    out = []
    for i in active:
        if out and i - out[-1][1] <= gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [(a, b) for a, b in out if (b - a) * SAMPLE_FRAMES / FPS >= MIN_FIGHT]


def fight_record(system: str, samples: list[dict], a: int, b: int, reloads: dict[str, tuple]) -> dict:
    first, last = samples[a], samples[b]
    seconds = (last["step"] - first["step"]) / FPS
    outfits = samples[0].get("outfits", {})
    shots = defaultdict(int)
    for s in samples[a + 1:b + 1]:
        for k, v in s["shots"].items():
            shots[k] += v
    ammo_used = {k: first["ammo"].get(k, 0) - last["ammo"].get(k, 0) for k in first["ammo"]}
    ammo_start = dict(first["ammo"])
    frac = lambda s, k: s[k] / s[k + "_max"] if s.get(k + "_max") else None
    energies = [frac(s, "energy") for s in samples[a:b + 1] if frac(s, "energy") is not None]
    heats = [frac(s, "heat") for s in samples[a:b + 1] if frac(s, "heat") is not None]
    # Ending: destroyed, disabled, jumped out (still alive), or survived in system.
    after = samples[b:min(len(samples), b + int(FIGHT_GAP * FPS / SAMPLE_FRAMES) + 1)]
    if any(s["destroyed"] for s in after):
        end = "destroyed"
    elif any(s["disabled"] for s in after):
        end = "disabled"
    elif any(s["jumping"] for s in after):
        end = "jumped"
    else:
        end = "survived"
    jump = next((s for s in samples[a:] if s["jumping"]), None)

    def health(s):
        top = s["shields_max"] + s["hull_max"] - s["hull_min"]
        return (s["shields"] + s["hull"] - s["hull_min"]) / top if top > 0 else None

    # Duty: shots × reload ÷ (fight frames × weapons installed), per weapon kind (primary, secondary, anti-missile).
    duty = {}
    frames = max(1., seconds * FPS)
    for kind in ("primary", "secondary"):
        fired = possible = 0.
        for name, count in outfits.items():
            if name not in reloads:
                continue
            reload, weapon_kind = reloads[name]
            if weapon_kind != kind:
                continue
            # Burst weapons can front-load shots in a short fight; count at most full duty per weapon.
            fired += min(shots.get(name, 0) * reload, frames * count)
            possible += frames * count
        duty[kind] = fired / possible if possible else None

    return {
        "system": system, "model": first["model"], "gov": first["gov"], "seconds": seconds,
        "category": samples[0].get("category", ""), "duty": duty,
        "ammo_full": dict(samples[0]["ammo"]),
        "shots": dict(shots), "ammo_start": ammo_start, "ammo_used": ammo_used,
        "energy_start": energies[0] if energies else None, "energy_min": min(energies) if energies else None,
        "heat_max": max(heats) if heats else None,
        "health_start": health(first), "health_end": health(last),
        "end": end, "jump_health": health(jump) if jump and end == "jumped" else None,
        "retreat": end == "jumped" and jump is not None and health(jump) is not None
                   and health(jump) < RETREAT_HEALTH,
        "fled": any(s["fleeing"] for s in samples[a:b + 1]),
    }


def quantiles(values: list[float], qs=(0.25, 0.5, 0.75)) -> list[float] | None:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return [values[min(len(values) - 1, int(q * len(values)))] for q in qs]


def weapon_reloads(resources: Path | None) -> dict[str, tuple[float, str]]:
    """Weapon outfit → (reload frames, "primary" / "secondary" / "anti-missile" / "other")."""
    if not resources:
        return {}
    sys.path.insert(0, str(ROOT))
    from es_optimizer import gamedata
    game = gamedata.load(resources)
    out = {}
    for name, outfit in game.outfits.items():
        weapon = outfit.weapon
        if not weapon:
            continue
        stats = weapon.stats
        if stats.get("anti-missile") or stats.get("tractor beam"):
            kind = "anti-missile"
        elif weapon.ammo:
            kind = "secondary"
        elif any(k.endswith("damage") for k in stats):
            kind = "primary"
        else:
            kind = "other"
        out[name] = (max(1., stats.get("reload", 1.)), kind)
    return out


def cmd_analyse(args) -> None:
    reloads = weapon_reloads(Path(args.resources) if args.resources else None)
    records = []
    observed = 0.
    for path in sorted(LOGS.glob("*.jsonl")):
        system = path.stem.rsplit("-", 1)[0].replace("_", " ")
        ships = load_samples(path)
        steps = [s["step"] for rows in ships.values() for s in rows]
        if steps:
            observed += (max(steps) - min(steps)) / FPS
        for rows in ships.values():
            for a, b in fights(rows):
                records.append(fight_record(system, rows, a, b, reloads))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fights.json").write_text(json.dumps(records, indent=0))

    summary = {"records": len(records), "observed_minutes": observed / 60,
               "by_government": group_rows(records, "gov"), "by_class": group_rows(records, "category")}
    lines = ["# War-zone observation: stock NPC fights", "",
             f"{len(records)} ship-fights over {observed / 60:.0f} observed game minutes "
             f"({len(list(LOGS.glob('*.jsonl')))} runs). Medians, with quartiles where shown. "
             "See tools/warzone/README.md for how a fight is cut.", ""]
    for title, key in (("By ship class", "by_class"), ("By government", "by_government")):
        lines += [f"## {title}", "", TABLE_HEAD, "|" + "---|" * 13]
        lines += [table_line(name, row) for name, row in summary[key].items()]
        lines.append("")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    (OUT / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


TABLE_HEAD = ("| Group | Fights | Length s | Primary duty | Secondary duty | Ammo used per fight (of full) "
              "| Fights of ammo carried | Energy low | Energy low, worst 10% | Heat peak | Heat peak, top 10% "
              "| Ends: destroyed / disabled / retreated / left | Health at retreat |")


def group_rows(records: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for r in records:
        groups[r[key] or "?"].append(r)
    out = {}
    for name, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        used_share, carried = [], []
        for r in rs:
            for k, full in r["ammo_full"].items():
                used = r["ammo_used"].get(k, 0)
                if full > 0:
                    used_share.append(used / full)
                    if used > 0:
                        carried.append(full / used)
        ends = defaultdict(int)
        for r in rs:
            ends[r["end"]] += 1
        out[name] = {
            "fights": len(rs),
            "seconds": quantiles([r["seconds"] for r in rs]),
            "primary_duty": quantiles([r["duty"].get("primary") for r in rs]),
            "secondary_duty": quantiles([r["duty"].get("secondary") for r in rs]),
            "ammo_used_share": quantiles(used_share),
            "fights_of_ammo": quantiles(carried),
            "energy_min": quantiles([r["energy_min"] for r in rs], (0.1, 0.5)),
            "heat_max": quantiles([r["heat_max"] for r in rs], (0.5, 0.9)),
            "ends": {k: v / len(rs) for k, v in ends.items()},
            "retreats": sum(r["retreat"] for r in rs) / len(rs),
            "retreat_health": quantiles([r["jump_health"] for r in rs if r["retreat"]]),
        }
    return out


def table_line(name: str, row: dict) -> str:
    def med(q, pct=True, spread=False):
        if not q:
            return "–"
        f = (lambda v: f"{v:.0%}") if pct else (lambda v: f"{v:.1f}" if v < 10 else f"{v:.0f}")
        return f"{f(q[1])} ({f(q[0])}–{f(q[2])})" if spread else f(q[1])
    e, h, ends = row["energy_min"], row["heat_max"], row["ends"]
    return (f"| {name} | {row['fights']} | {med(row['seconds'], False, True)} | {med(row['primary_duty'])} "
            f"| {med(row['secondary_duty'])} | {med(row['ammo_used_share'])} | {med(row['fights_of_ammo'], False, True)} "
            f"| {e[1]:.0%} | {e[0]:.0%} | {h[0]:.0%} | {h[1]:.0%} "
            f"| {ends.get('destroyed', 0):.0%} / {ends.get('disabled', 0):.0%} / {row['retreats']:.0%} "
            f"/ {ends.get('jumped', 0) - row['retreats']:.0%} | {med(row['retreat_health'], spread=True)} |") if e and h else f"| {name} | {row['fights']} | – |"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plugin")
    p.add_argument("--resources", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--minutes", type=float, default=20)
    p.set_defaults(func=cmd_plugin)
    p = sub.add_parser("run")
    p.add_argument("--game", required=True)
    p.add_argument("--resources", required=True)
    p.add_argument("--minutes", type=float, default=20, help="game minutes per run (Korath systems get 3x)")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--systems", nargs="*")
    p.add_argument("--parallel", type=int, default=1)
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("analyse")
    p.add_argument("--resources", help="game folder, for weapon reload times (weapon duty)")
    p.set_defaults(func=cmd_analyse)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
