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
    # Alien war zones (the vulture roles): Hai vs Hai Unfettered, Kor Mereti vs Kor Sestor.
    "Wah Ki": 1, "Mesuket": 1,
}
# The save must name a planet. Beta Lupi, Lesath, Durax and Mesuket have none, so the player "lands" on a stand-in; the
# engine then places the departing flagship in the save's system (its fallback for a planet not in the system).
PLANETS = {"Nunki": "Albatross", "Shaula": "Greenrock", "Almaaz": "Freedom", "Misam": "New Tortuga",
           "Polaris": "Shangri-La", "Wah Ki": "Cloudfire"}
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
#
# A fight is fleet against fleet (the user's definition). A fleet is a leader plus the ships whose parent chain
# leads to it (escorts, and fighters through their carrier). Two fleets are engaged while a member of one targets
# a member of the other and fires or is within ENGAGE_RANGE; samples less than FIGHT_GAP apart join up, and an
# engagement needs at least one shot. A fleet's fight is the union of its engagements that overlap or come less
# than FIGHT_GAP apart, so one fight can be against several fleets at once or back to back without a breather:
# the case a player meets (1–3 fleets).

WEAPON_KINDS = ("gun", "turret", "secondary")


def load_samples(path: Path, yours: bool = False) -> dict[str, list[dict]]:
    ships = defaultdict(list)
    with path.open() as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut off when the run ended
            # Frame and order lines have no ship id; the player's own ships (the watcher) are left out unless asked.
            if "id" in row and (yours or not row.get("yours")):
                ships[row["id"]].append(row)
    return ships


def fleets(ships: dict[str, list[dict]]) -> dict[str, str]:
    """Ship id → fleet id (the root of its first-seen parent chain)."""
    parent = {sid: next((r["parent"] for r in rows if r.get("parent")), "") for sid, rows in ships.items()}

    def root(sid):
        seen = set()
        while parent.get(sid) and sid not in seen:
            seen.add(sid)
            sid = parent[sid]
        return sid
    return {sid: root(sid) for sid in ships}


def merge(steps: list[tuple[int, bool]]) -> list[tuple[int, int]]:
    """(step, fired) samples → [start, end] windows with at least one shot, gaps under FIGHT_GAP joined."""
    out = []
    for step, fired in sorted(steps):
        if out and step - out[-1][1] <= FIGHT_GAP * FPS:
            out[-1][1] = step
            out[-1][2] |= fired
        else:
            out.append([step, step, fired])
    return [(a, b) for a, b, fired in out if fired]


def fleet_fights(ships: dict[str, list[dict]], fleet: dict[str, str]) -> list[dict]:
    pair_steps = defaultdict(list)
    for sid, rows in ships.items():
        own = fleet[sid]
        for r in rows:
            if r["disabled"] or r["destroyed"] or r["target"] < 0 or not r.get("target_id"):
                continue
            other = fleet.get(r["target_id"], r["target_id"])
            if other == own:
                continue
            fired = any(r["shots"].values())
            if fired or r["target"] <= ENGAGE_RANGE:
                pair_steps[tuple(sorted((own, other)))].append((r["step"], fired))
    # Engagements per fleet, then joined into that fleet's fights.
    per_fleet = defaultdict(list)
    for (f1, f2), steps in pair_steps.items():
        for start, end in merge(steps):
            per_fleet[f1].append((start, end, f2))
            per_fleet[f2].append((start, end, f1))
    fights = []
    for own, engagements in per_fleet.items():
        current = None
        for start, end, other in sorted(engagements):
            if current and start - current["end"] <= FIGHT_GAP * FPS:
                current["end"] = max(current["end"], end)
                current["opponents"].add(other)
                current["engagements"].append((start, end))
            else:
                current = {"fleet": own, "start": start, "end": end, "opponents": {other},
                           "engagements": [(start, end)]}
                fights.append(current)
    return [f for f in fights if (f["end"] - f["start"]) / FPS >= MIN_FIGHT]


def most_at_once(engagements: list[tuple[int, int]]) -> int:
    """The most engagements (opposing fleets) running at the same moment."""
    events = sorted([(a, 1) for a, _ in engagements] + [(b, -1) for _, b in engagements], key=lambda e: (e[0], -e[1]))
    best = current = 0
    for _, change in events:
        current += change
        best = max(best, current)
    return best


def ship_window(rows: list[dict], start: int, end: int) -> tuple[int, int] | None:
    """Index range of this ship's samples inside [start, end], cut at its first disabled or destroyed sample."""
    idx = [i for i, r in enumerate(rows) if start <= r["step"] <= end]
    if not idx:
        return None
    a, b = idx[0], idx[-1]
    for i in range(a, b + 1):
        if rows[i]["disabled"] or rows[i]["destroyed"]:
            b = i
            break
    return (a, b) if b > a else None


def health(s):
    top = s["shields_max"] + s["hull_max"] - s["hull_min"]
    return (s["shields"] + s["hull"] - s["hull_min"]) / top if top > 0 else None


def ship_record(samples: list[dict], a: int, b: int, weapons: dict[str, tuple]) -> dict:
    first, last = samples[a], samples[b]
    seconds = (last["step"] - first["step"]) / FPS
    outfits = samples[0].get("outfits", {})
    shots = defaultdict(int)
    for s in samples[a + 1:b + 1]:
        for k, v in s["shots"].items():
            shots[k] += v
    ammo_used = {k: first["ammo"].get(k, 0) - last["ammo"].get(k, 0) for k in first["ammo"]}
    frac = lambda s, k: s[k] / s[k + "_max"] if s.get(k + "_max") else None
    energies = [frac(s, "energy") for s in samples[a:b + 1] if frac(s, "energy") is not None]
    heats = [frac(s, "heat") for s in samples[a:b + 1] if frac(s, "heat") is not None]
    after = samples[b:min(len(samples), b + int(FIGHT_GAP * FPS / SAMPLE_FRAMES) + 1)]
    if any(s["destroyed"] for s in after):
        end = "destroyed"
    elif any(s["disabled"] for s in after):
        end = "disabled"
    elif any(s["jumping"] for s in after):
        end = "jumped"
    else:
        end = "stayed"
    jump = next((s for s in after if s["jumping"]), None)
    jump_health = health(jump) if jump and end == "jumped" else None

    # Duty: shots × reload ÷ (frames × weapons installed), per weapon kind. Burst weapons can front-load shots in
    # a short window, so each weapon counts at most full duty.
    duty = {}
    frames = max(1., seconds * FPS)
    for kind in WEAPON_KINDS:
        fired = possible = 0.
        for name, count in outfits.items():
            if name in weapons and weapons[name][1] == kind:
                fired += min(shots.get(name, 0) * weapons[name][0], frames * count)
                possible += frames * count
        duty[kind] = fired / possible if possible else None

    return {
        "model": first["model"], "yours": bool(first.get("yours")), "gov": first["gov"],
        "category": samples[0].get("category", ""),
        "seconds": seconds, "duty": duty,
        "ammo_full": dict(samples[0]["ammo"]), "ammo_start": dict(first["ammo"]), "ammo_used": ammo_used,
        "energy_min": min(energies) if energies else None, "heat_max": max(heats) if heats else None,
        "health_start": health(first), "health_end": health(last), "end": end, "jump_health": jump_health,
        "retreat": jump_health is not None and jump_health < RETREAT_HEALTH,
    }


def quantiles(values: list[float], qs=(0.25, 0.5, 0.75)) -> list[float] | None:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return [values[min(len(values) - 1, int(q * len(values)))] for q in qs]


def weapon_kinds(resources: Path | None) -> dict[str, tuple[float, str]]:
    """Weapon outfit → (reload frames, kind): gun, turret, secondary (uses ammo), anti-missile, other."""
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
        # By the outfit's own category: damage often comes from submunitions (Ka'het weapons), not the weapon itself.
        if stats.get("anti-missile") or stats.get("tractor beam"):
            kind = "anti-missile"
        elif weapon.ammo or outfit.category == "Secondary Weapons":
            kind = "secondary"
        elif outfit.category == "Turrets":
            kind = "turret"
        elif outfit.category == "Guns":
            kind = "gun"
        else:
            kind = "other"
        out[name] = (max(1., stats.get("reload", 1.)), kind)
    return out


def analyse_run(system: str, ships: dict[str, list[dict]], weapons: dict) -> list[dict]:
    fleet = fleets(ships)
    members = defaultdict(list)
    for sid, f in fleet.items():
        members[f].append(sid)
    gov_of = lambda sid: ships[sid][0]["gov"] if sid in ships else "?"
    records = []
    for fight in fleet_fights(ships, fleet):
        crew = []
        for sid in members[fight["fleet"]]:
            window = ship_window(ships[sid], fight["start"], fight["end"])
            if window:
                crew.append(ship_record(ships[sid], *window, weapons))
        if not crew:
            continue
        opponents = sorted(fight["opponents"])
        enemy_ships = sum(1 for o in opponents for sid in members.get(o, [o])
                          if sid in ships and ship_window(ships[sid], fight["start"], fight["end"]))
        records.append({
            "system": system, "gov": gov_of(fight["fleet"]),
            "leader": ships[fight["fleet"]][0]["model"] if fight["fleet"] in ships else "?",
            "seconds": (fight["end"] - fight["start"]) / FPS,
            "opponents": len(opponents),
            "at_once": most_at_once(fight["engagements"]),
            "own_ships": len(crew), "enemy_ships": enemy_ships,
            "opponent_govs": sorted({gov_of(o) for o in opponents}),
            "ships": crew,
        })
    return records


def cmd_analyse(args) -> None:
    weapons = weapon_kinds(Path(args.resources) if args.resources else None)
    records = []
    observed = 0.
    runs = sorted(LOGS.glob("*.jsonl"))
    for path in runs:
        system = path.stem.rsplit("-", 1)[0].replace("_", " ")
        ships = load_samples(path)
        steps = [s["step"] for rows in ships.values() for s in rows]
        if steps:
            observed += (max(steps) - min(steps)) / FPS
        records += analyse_run(system, ships, weapons)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fights.json").write_text(json.dumps(records, indent=0))

    ship_rows = [dict(r, fleet_gov=f["gov"]) for f in records for r in f["ships"]]
    summary = {
        "fleet_fights": len(records), "ship_fights": len(ship_rows), "observed_minutes": observed / 60,
        "fleets_by_government": fleet_rows(records, lambda f: f["gov"]),
        "fleets_by_opponents": fleet_rows(records, lambda f: str(min(f["opponents"], 3)) + ("+" if f["opponents"] >= 3 else "")),
        "fleets_by_at_once": fleet_rows(records, lambda f: str(min(f["at_once"], 3)) + ("+" if f["at_once"] >= 3 else "")),
        "fleets_by_system": fleet_rows(records, lambda f: f["system"]),
        "ships_by_class": ship_groups(ship_rows, "category"),
        "ships_by_government": ship_groups(ship_rows, "gov"),
    }
    lines = ["# War-zone observation: stock NPC fights, fleet against fleet", "",
             f"{len(records)} fleet fights ({len(ship_rows)} ship records) over {observed / 60:.0f} observed game "
             f"minutes ({len(runs)} runs). Medians, with quartiles in brackets. How a fight is cut: "
             "tools/warzone/README.md.", ""]
    for title, key in (("Fleet fights by government", "fleets_by_government"),
                       ("Fleet fights by number of opposing fleets over the fight", "fleets_by_opponents"),
                       ("Fleet fights by most opposing fleets at the same time", "fleets_by_at_once"),
                       ("Fleet fights by system", "fleets_by_system")):
        lines += [f"## {title}", "", FLEET_HEAD, "|" + "---|" * 9]
        lines += [fleet_line(name, row) for name, row in summary[key].items()]
        lines.append("")
    for title, key in (("Ships in fleet fights, by class", "ships_by_class"),
                       ("Ships in fleet fights, by government", "ships_by_government")):
        lines += [f"## {title}", "", SHIP_HEAD, "|" + "---|" * 14]
        lines += [ship_line(name, row) for name, row in summary[key].items()]
        lines.append("")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    (OUT / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


FLEET_HEAD = ("| Group | Fights | Length s | Opposing fleets over the fight: 1 / 2 / 3+ "
              "| Most at the same time: 1 / 2 / 3+ | Own ships | Enemy ships | "
              "Own ships lost (destroyed or disabled) | Own ships retreated |")


def fleet_rows(records: list[dict], key) -> dict:
    groups = defaultdict(list)
    for f in records:
        groups[key(f)].append(f)
    out = {}
    for name, fs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        n = len(fs)
        lost = [sum(s["end"] in ("destroyed", "disabled") for s in f["ships"]) / len(f["ships"]) for f in fs]
        fled = [sum(s["retreat"] for s in f["ships"]) / len(f["ships"]) for f in fs]
        out[name] = {
            "fights": n, "seconds": quantiles([f["seconds"] for f in fs]),
            "opponents": [sum(f["opponents"] == 1 for f in fs) / n, sum(f["opponents"] == 2 for f in fs) / n,
                          sum(f["opponents"] >= 3 for f in fs) / n],
            "at_once": [sum(f["at_once"] == 1 for f in fs) / n, sum(f["at_once"] == 2 for f in fs) / n,
                        sum(f["at_once"] >= 3 for f in fs) / n],
            "ships": quantiles([f["own_ships"] for f in fs]),
            "enemy_ships": quantiles([f["enemy_ships"] for f in fs]),
            "lost": sum(lost) / n, "retreated": sum(fled) / n,
        }
    return out


def fmt_q(q, pct=True, spread=False):
    if not q:
        return "–"
    f = (lambda v: f"{v:.0%}") if pct else (lambda v: f"{v:.1f}" if v < 10 else f"{v:.0f}")
    return f"{f(q[1])} ({f(q[0])}–{f(q[2])})" if spread else f(q[1])


def fleet_line(name: str, row: dict) -> str:
    o, c = row["opponents"], row["at_once"]
    return (f"| {name} | {row['fights']} | {fmt_q(row['seconds'], False, True)} "
            f"| {o[0]:.0%} / {o[1]:.0%} / {o[2]:.0%} | {c[0]:.0%} / {c[1]:.0%} / {c[2]:.0%} "
            f"| {fmt_q(row['ships'], False, True)} | {fmt_q(row['enemy_ships'], False, True)} | {row['lost']:.0%} "
            f"| {row['retreated']:.0%} |")


SHIP_HEAD = ("| Group | Ship records | Time in fight s | Gun duty | Turret duty | Secondary duty "
             "| Ammo used per fight (of full) | Fights of ammo carried | Energy low | Energy low, worst 10% "
             "| Heat peak | Heat peak, top 10% | Ends: destroyed / disabled / retreated / left | Health at retreat |")


def ship_groups(rows: list[dict], key: str) -> dict:
    groups = defaultdict(list)
    for r in rows:
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
            "records": len(rs), "seconds": quantiles([r["seconds"] for r in rs]),
            **{f"{k}_duty": quantiles([r["duty"].get(k) for r in rs]) for k in WEAPON_KINDS},
            "ammo_used_share": quantiles(used_share), "fights_of_ammo": quantiles(carried),
            "energy_min": quantiles([r["energy_min"] for r in rs], (0.1, 0.5)),
            "heat_max": quantiles([r["heat_max"] for r in rs], (0.5, 0.9)),
            "ends": {k: v / len(rs) for k, v in ends.items()},
            "retreats": sum(r["retreat"] for r in rs) / len(rs),
            "retreat_health": quantiles([r["jump_health"] for r in rs if r["retreat"]]),
        }
    return out


def ship_line(name: str, row: dict) -> str:
    e, h, ends = row["energy_min"], row["heat_max"], row["ends"]
    pct = lambda q, i: f"{q[i]:.0%}" if q else "–"      # no battery: no energy fraction
    return (f"| {name} | {row['records']} | {fmt_q(row['seconds'], False, True)} | {fmt_q(row['gun_duty'])} "
            f"| {fmt_q(row['turret_duty'])} | {fmt_q(row['secondary_duty'])} | {fmt_q(row['ammo_used_share'])} "
            f"| {fmt_q(row['fights_of_ammo'], False, True)} | {pct(e, 1)} | {pct(e, 0)} | {pct(h, 0)} | {pct(h, 1)} "
            f"| {ends.get('destroyed', 0):.0%} / {ends.get('disabled', 0):.0%} / {row['retreats']:.0%} "
            f"/ {ends.get('jumped', 0) - row['retreats']:.0%} | {fmt_q(row['retreat_health'], spread=True)} |")


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
    p.add_argument("--resources", help="game folder, for weapon reload times and gun/turret kinds (duty)")
    p.set_defaults(func=cmd_analyse)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
