"""Calibration batch: many hulls × roles with full visibility, tipping-point probes, and a stock-ship anchor.

    python tools/calibrate.py plan            # write experiments/calibration/plan.json
    python tools/calibrate.py run --parallel 2  # run every job not yet done (resumable)
    python tools/calibrate.py run --parallel 6 --alarm --keep-awake   # on a 12-core desktop
    python tools/calibrate.py stock           # stock ships against the rules, swept over the tunables
    python tools/calibrate.py job ID          # one job (used by run)

Results: experiments/calibration/jobs/<id>.json (insight.record + class report + probes), stock.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from es_optimizer import calculator, insight, roles, solver, tuning  # noqa: E402
from es_optimizer.availability import Availability, source_group  # noqa: E402
from es_optimizer.storage import Store, default_home  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "experiments" / "calibration"

# Roles per ship class for the run set.
CLASS_ROLES = {
    "Heavy Warship": [["warship"], ["tank"], ["missile-boat"], ["fight-anchor"], ["sniper"]],
    "Medium Warship": [["warship"], ["escort"], ["tank"], ["missile-boat"], ["fight-anchor"]],
    "Light Warship": [["escort"], ["dogfighter"], ["brawler"], ["point-defense"], ["anti-fighter"]],
    "Interceptor": [["interceptor"], ["escort"]],
    "Light Freighter": [["freighter"], ["freighter", "escort"], ["smuggler"], ["courier"]],
    "Heavy Freighter": [["freighter"], ["peaceful-freighter"], ["freighter", "escort"]],
    "Transport": [["liner"], ["courier"], ["freighter"]],
    "Space Liner": [["liner"], ["boarder"]],
    "Utility": [["scavenger"], ["boarder"], ["freighter"]],
}
PER_CLASS = 4            # hulls per class: spread over mass
EXTRA_HULLS = ["Kar Ik Vot 349", "Argosy"]
CLOAK_ROLES = [["vulture"], ["vulture-mesuket"]]
# Tipping-point probes: tunable -> values (the current value is the baseline).
PROBES = {
    "FIGHTS": [{"escort": 45, "dedicated": 120}, {"escort": 60, "dedicated": 180}, {"escort": 120, "dedicated": 360}],
    "CRUISE_THRUST": [0.3, 0.5],
    "SECONDARY_SHARE": [0.5, 1.0],
    "PRIMARY_SHARE": [0.7, 0.5],
    "MAGAZINE_WINDOW": [{"90": 1.0, "240": 1.0}, {"90": 0.75, "240": 0.6}],
    "HEAT_TARGET": [0.8, 1.0],
    "COMBAT_MIN_SHOTS": [3.0, 1.0],
    "GUN_FULL_AGILITY": [80.0, 50.0],
    "TURRET_TURN_FULL": [75.0],
    "PROJECTILE_SPEED_FULL": [300.0],
    "RECOVERY_LONG": [1.0, 2.0],
}
PROBE_WEIGHTS = {"firepower": [0.4, 0.6]}      # --emphasize firepower=share
PROBE_BALANCE = [0.3, 0.6]                     # deviation weighting strength


def load():
    home = Path(os.environ.get("ES_HOME") or default_home())
    store = Store(home)
    return home, store.load_catalog(), store.load_settings()


def choose_hulls(game, settings) -> list[tuple[str, str]]:
    """(hull, category): per class, PER_CLASS available stock hulls spread over mass; plus extras and cloakers."""
    available = Availability(game, settings)
    by_class: dict[str, list] = {}
    for h in game.hulls.values():
        if (h.category in CLASS_ROLES and not h.deprecated and h.stock_outfits and h.has_sprite
                and source_group(h) != "scripted" and available.hull_ok(h)
                and not h.name.startswith(("Aberrant", "Asteroid"))):
            ship = calculator.build(game, h, h.stock_outfits)
            if not ship.fit_errors:
                by_class.setdefault(h.category, []).append((ship.mass, h.name))
    chosen = []
    for category, rows in by_class.items():
        rows.sort()
        n = len(rows)
        picks = sorted({round(i * (n - 1) / max(1, PER_CLASS - 1)) for i in range(min(PER_CLASS, n))})
        chosen += [(rows[i][1], category) for i in picks]
    for name in EXTRA_HULLS:
        h = game.hulls.get(name)
        if h and (name, h.category) not in chosen:
            chosen.append((name, h.category))
    return chosen


def make_plan(game, settings) -> list[dict]:
    jobs = []
    probe_hulls = set()
    hulls = choose_hulls(game, settings)
    # Probe hulls: the first hull of each class with a combat role, plus the extras (the "starting 10").
    seen = set()
    for name, category in hulls:
        if category not in seen or name in EXTRA_HULLS:
            seen.add(category)
            probe_hulls.add(name)
    for name, category in hulls:
        for i, role_set in enumerate(CLASS_ROLES.get(category, [])):
            job = {"id": f"{name}--{'+'.join(role_set)}", "hull": name, "roles": role_set,
                   "probes": name in probe_hulls and i == 0, "priority": 0 if i == 0 else 1}
            jobs.append(job)
    for h in game.hulls.values():
        if h.attributes.get("cloak", 0) > 0 and h.category in CLASS_ROLES and Availability(game, settings).hull_ok(h):
            for role_set in CLOAK_ROLES:
                jobs.append({"id": f"{h.name}--{'+'.join(role_set)}", "hull": h.name, "roles": role_set,
                             "probes": False, "priority": 1})
    jobs.sort(key=lambda j: (j["priority"], j["id"]))
    return jobs


# Phase 2: full re-solves on the probe hulls' first role under alternative settings, to confirm what the probes
# (re-polishes from the baseline) suggest.
VARIANTS = {
    "primaries 60%": {"tuning": {"PRIMARY_SHARE": 0.6}},
    "primaries 60%, balance 0.5": {"tuning": {"PRIMARY_SHARE": 0.6}, "balance": 0.5},
    "balance 0.5": {"balance": 0.5},
    "firepower 50%": {"emphasize": ["firepower=0.5"]},
    "weapon tweaks": {"weapon_tweaks": True},
    "reference all": {"reference": "all"},
    "fights 60/150": {"tuning": {"FIGHTS": {"escort": 60, "dedicated": 150}}},
    "primaries 60%, tweaks, firepower 50%": {"tuning": {"PRIMARY_SHARE": 0.6}, "weapon_tweaks": True,
                                            "emphasize": ["firepower=0.5"]},
    "secondaries 100% window": {"tuning": {"MAGAZINE_WINDOW": {"90": 1.0, "240": 1.0}, "SECONDARY_SHARE": 1.0}},
    "min shots 2": {"tuning": {"COMBAT_MIN_SHOTS": 2.0}},
    "gun agility 60": {"tuning": {"GUN_FULL_AGILITY": 60.0}},
    "heat target 100%": {"tuning": {"HEAT_TARGET": 1.0}},
}


def phase2(plan: list[dict]) -> list[dict]:
    base = [j for j in plan if j.get("probes") and "variant" not in j]
    extra = []
    for j in base:
        for label, change in VARIANTS.items():
            extra.append({**j, **change, "id": f"{j['id']}--{label}", "variant": label, "probes": False,
                          "priority": 2, "class report": False})
    have = {j["id"] for j in plan}
    return plan + [e for e in extra if e["id"] not in have]


def run_job(job: dict, home, game, settings) -> dict:
    hull = game.hulls.get(job["hull"]) or game.variants.get(job["hull"])
    request = roles.combine([roles.load_role(r, home) for r in job["roles"]], roles.shared_metrics(home), game,
                            job.get("emphasize", []), job.get("deprioritize", []))
    request.balance = job.get("balance", 0.0)
    request.role.weapon_tweaks = job.get("weapon_tweaks", False)
    if "reference" in job:
        request.reference = job["reference"]
    with tuning.override(job.get("tuning", {})):
        start = time.monotonic()
        result = solver.optimize(game, hull, request, settings, seconds_per_solve=job.get("seconds", 2.0),
                                 polish_seconds=job.get("polish", 40.0), jobs=job.get("jobs", 2),
                                 threads=job.get("threads", 1))
        rec = insight.record(game, hull, request, result, {"job": job})
        if result.design is not None and job.get("class report", True):
            rec["class report"] = insight.class_report(result, seconds=job.get("class seconds", 5.0))
            if job.get("probes"):
                probes = []
                for name, values in PROBES.items():
                    for value in values:
                        probes.append({"knob": name, "value": value, **insight.probe(result, {name: value})})
                for share in PROBE_WEIGHTS["firepower"]:
                    req2 = roles.combine([roles.load_role(r, home) for r in job["roles"]],
                                         roles.shared_metrics(home), game, [f"firepower={share}"])
                    probes.append({"knob": "firepower share", "value": share,
                                   **_reweighted_probe(result, req2)})
                for alpha in PROBE_BALANCE:
                    old = request.balance
                    request.balance = alpha
                    probes.append({"knob": "balance strength", "value": alpha, **insight.probe(result, {})})
                    request.balance = old
                rec["probes"] = probes
        rec["wall seconds"] = time.monotonic() - start
    return rec


def _reweighted_probe(result, request2) -> dict:
    """Re-polish under different role weights (the same scales and pool)."""
    ctx = result.context
    request2.role = ctx.request.role
    request2.balance = ctx.request.balance
    scorer = solver.Scorer(request2, ctx.scales)
    missing = [m for m in request2.metrics if m not in ctx.scales]
    if missing:
        return {"skipped": "metrics without scales: " + ", ".join(missing)}
    judge = lambda outfits, ship=None: solver.evaluate_design(ctx.game, ctx.hull, outfits, request2, scorer,
                                                              ctx.disruption, ctx.capture_targets, ship)
    start = judge(result.design.outfits)
    polished, moves = solver.polish(ctx.game, ctx.hull, ctx.pool, ctx.bounds, start, judge, 10.0)
    return {"moves": moves, "design": insight.design_summary(ctx.game, polished, request2)}


STOCK_SWEEPS = {
    "baseline": {},
    "fight 60/120": {"FIGHTS": {"escort": 60, "dedicated": 120}},
    "fight 90/180": {"FIGHTS": {"escort": 90, "dedicated": 180}},
    "fight 45/90": {"FIGHTS": {"escort": 45, "dedicated": 90}},
    "thrust 50%": {"CRUISE_THRUST": 0.5},
    "thrust 30%": {"CRUISE_THRUST": 0.3},
    "heat 100%": {"HEAT_TARGET": 1.0},
    "secondaries 50%": {"SECONDARY_SHARE": 0.5},
    "recovery 1.0": {"RECOVERY_LONG": 1.0},
    "primaries 70%": {"PRIMARY_SHARE": 0.7},
    "primaries 50%": {"PRIMARY_SHARE": 0.5},
    "primaries 70%, fight 90/180": {"PRIMARY_SHARE": 0.7, "FIGHTS": {"escort": 90, "dedicated": 180}},
}
STOCK_ROLE = {"Heavy Warship": "warship", "Medium Warship": "warship", "Light Warship": "escort",
              "Interceptor": "interceptor", "Light Freighter": "freighter", "Heavy Freighter": "freighter",
              "Transport": "liner", "Space Liner": "liner", "Utility": "scavenger"}


def stock_anchor(home, game, settings) -> dict:
    rows = []
    reference = solver.reference_weapons(game, settings)
    agility = solver.stock_agility(game)
    for h in list(game.hulls.values()) + list(game.variants.values()):
        if h.category not in STOCK_ROLE or h.deprecated or not h.stock_outfits or not h.has_sprite:
            continue
        if source_group(h) == "scripted":
            continue
        ship = calculator.build(game, h, h.stock_outfits)
        if ship.fit_errors:
            continue
        request = roles.combine([roles.load_role(STOCK_ROLE[h.category], home)], roles.shared_metrics(home), game)
        request.role.reference_weapons, request.role.stock_agility = reference, agility
        row = {"hull": h.name, "category": h.category, "source": source_group(h),
               "governments": sorted(g for g, ships in game.government_ships.items() if h.name in ships),
               "role": STOCK_ROLE[h.category], "sweeps": {}}
        b = solver.balance(game, ship)
        u = insight.usage(game, ship.outfits)
        row["weapon capacity used"] = b["weapon capacity used"]
        row["batteries"] = u["batteries"]["count"]
        row["battery capacity added"] = ship.get("energy capacity") - h.attributes.get("energy capacity", 0.0)
        row["secondaries"] = u["secondaries"]["count"]
        row["secondary share"] = roles.metric_value(ship, request.role, "secondary share")
        row["usage"] = {c: v["outfit space"] for c, v in u.items()}
        for label, overrides in STOCK_SWEEPS.items():
            with tuning.override(overrides):
                req = roles.combine([roles.load_role(STOCK_ROLE[h.category], home)], roles.shared_metrics(home), game)
                req.role.reference_weapons, req.role.stock_agility = reference, agility
                checks = roles.check_request(ship, req, game) + calculator.evaluate(ship, req.role)
                row["sweeps"][label] = {"failed": [c.name for c in checks if c.passed is False],
                                        **insight.check_numbers(checks)}
        rows.append(row)
    return {"tuning": tuning.snapshot(), "ships": rows}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--phase", type=int, default=1, help="2: add full re-solves under alternative settings.")
    run = sub.add_parser("run")
    run.add_argument("--parallel", type=int, default=2)
    run.add_argument("--only", default="", help="Only job ids containing this text.")
    run.add_argument("--alarm", action="store_true", help="Sound an alarm when the run finishes (or stops).")
    run.add_argument("--keep-awake", action="store_true",
                     help="Keep the computer from sleeping while the run lasts (systemd-inhibit or caffeinate).")
    job = sub.add_parser("job")
    job.add_argument("id")
    sub.add_parser("stock")
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "jobs").mkdir(exist_ok=True)
    plan_path = OUT / "plan.json"

    if args.command == "plan":
        home, game, settings = load()
        plan = make_plan(game, settings) if args.phase == 1 else phase2(json.loads(plan_path.read_text()))
        plan_path.write_text(json.dumps(plan, indent=1))
        print(f"{len(plan)} jobs, {sum(j['probes'] for j in plan)} with probes -> {plan_path}")
        return 0
    if args.command == "stock":
        home, game, settings = load()
        data = stock_anchor(home, game, settings)
        (OUT / "stock.json").write_text(json.dumps(data, indent=1))
        print(f"{len(data['ships'])} stock ships -> {OUT / 'stock.json'}")
        return 0
    plan = json.loads(plan_path.read_text())
    if args.command == "job":
        home, game, settings = load()
        entry = next(j for j in plan if j["id"] == args.id)
        rec = run_job(entry, home, game, settings)
        (OUT / "jobs" / f"{_safe(entry['id'])}.json").write_text(json.dumps(rec, indent=1, default=str))
        return 0
    # run: subprocesses, resumable.
    if args.keep_awake and not os.environ.get("ES_CALIBRATE_AWAKE"):
        command = keep_awake_command()
        if command:
            os.environ["ES_CALIBRATE_AWAKE"] = "1"
            print("keep-awake: " + " ".join(command[:2]) + " (the computer won't sleep until the run ends)", flush=True)
            return subprocess.call(command + [sys.executable, __file__] + (argv if argv is not None else sys.argv[1:]))
        print("keep-awake: no working systemd-inhibit or caffeinate here; the computer may sleep", flush=True)
    try:
        failed = run_all(args, plan)
    finally:
        if args.alarm:
            alarm()
    return 1 if failed else 0


def run_all(args, plan) -> int:
    pending = [j for j in plan if not (OUT / "jobs" / f"{_safe(j['id'])}.json").exists() and args.only in j["id"]]
    print(f"{len(pending)} jobs to run", flush=True)
    running: list[tuple[subprocess.Popen, dict, float]] = []
    failed = 0
    while pending or running:
        while pending and len(running) < args.parallel:
            j = pending.pop(0)
            log = open(OUT / "jobs" / f"{_safe(j['id'])}.log", "w")
            p = subprocess.Popen([sys.executable, __file__, "job", j["id"]], stdout=log, stderr=subprocess.STDOUT)
            running.append((p, j, time.monotonic()))
        time.sleep(2)
        for p, j, t in list(running):
            if p.poll() is not None:
                running.remove((p, j, t))
                failed += p.returncode != 0
                print(f"{'done' if p.returncode == 0 else 'FAILED'} {j['id']} ({time.monotonic() - t:.0f} s)",
                      flush=True)
    left = sum(1 for j in plan if not (OUT / "jobs" / f"{_safe(j['id'])}.json").exists())
    print(f"finished: {failed} failed, {left} of {len(plan)} jobs without a result", flush=True)
    return failed


def keep_awake_command() -> list[str] | None:
    """A wrapper that keeps the computer awake while the wrapped command runs, if one works here (tried first with a
    command that does nothing)."""
    candidates = []
    if shutil.which("systemd-inhibit"):
        candidates.append(["systemd-inhibit", "--what=sleep:idle", "--who=es-optimizer calibration",
                           "--why=Calibration batch running", "--mode=block"])
    if shutil.which("caffeinate"):
        candidates.append(["caffeinate", "-i"])
    for command in candidates:
        try:
            if subprocess.call(command + ["true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10) == 0:
                return command
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


ALARM_SOUNDS = ["/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga",
                "/usr/share/sounds/freedesktop/stereo/complete.oga",
                "/usr/share/sounds/freedesktop/stereo/bell.oga"]


def alarm(seconds: float = 30.0) -> None:
    """Sound an alarm for about `seconds`: paplay with a freedesktop sound, else canberra-gtk-play, else the bell."""
    sound = next((s for s in ALARM_SOUNDS if Path(s).exists()), None)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        played = False
        try:
            if sound and shutil.which("paplay"):
                played = subprocess.call(["paplay", sound], stderr=subprocess.DEVNULL) == 0
            elif shutil.which("canberra-gtk-play"):
                played = subprocess.call(["canberra-gtk-play", "-i", "alarm-clock-elapsed"],
                                         stderr=subprocess.DEVNULL) == 0
        except OSError:
            played = False
        if not played:
            print("\a", end="", flush=True)
            time.sleep(1.0)


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-+_." else "_" for c in name)


if __name__ == "__main__":
    sys.exit(main())
