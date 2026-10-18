"""Run scoring experiments: every combination of reference mode, combine mode and weapon tweaks, on a few hulls,
and measure each design against the hull's stock design on raw numbers.

    python tools/experiment.py --home path/to/tool/home --out runs/experiments [--runs 2] [--tweaks both]

One JSON file per run in --out (finished runs are skipped when restarted), then `--report` writes a summary.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from es_optimizer import calculator, roles, solver  # noqa: E402
from es_optimizer.storage import Store  # noqa: E402

HULLS = ["Kar Ik Vot 349", "Argosy", "Firebird"]
REFERENCES = ["legacy", "all", "family", "class", "stock"]
COMBINES = ["sum", "power:0.5", "power:0"]
# Weight variants: default; firepower at 65% of the score; the evasive branch without top speed.
WEIGHTS = {"default": ([], {}), "firepower65": (["firepower=0.65"], {}),
           "evasive-lite": ([], {"evasive": {"agility": 2.0, "anti-missile": 1.0}}),
           "fp65-lite": (["firepower=0.65"], {"evasive": {"agility": 2.0, "anti-missile": 1.0}})}


def measure(game, hull, outfits: dict[str, int]) -> dict:
    """Raw numbers that don't depend on the scoring rules."""
    s = calculator.build(game, hull, outfits)
    off = [w for w in s.weapons if w.offensive]
    b = solver.balance(game, s)
    secondary = sum(c for n, c in outfits.items() if game.outfits[n].category == "Secondary Weapons"
                    and game.outfits[n].weapon is not None)
    return {
        "raw dps": 60 * sum(w.shield_damage + w.hull_damage for w in off),
        "guns": sum(w.count for w in off if not w.turret),
        "turrets": sum(w.count for w in s.weapons if w.turret),
        "secondary weapons": secondary,
        "shield regen": s.shield_regen * 60, "hull repair": s.hull_repair * 60,
        "anti-missile": sum(w.anti_missile * w.count for w in s.weapons if w.anti_missile),
        "pull": -60 * sum(w.hit_force for w in s.weapons if w.hit_force < 0),
        "turn": s.turn_rate, "acceleration": s.acceleration, "speed": s.max_speed,
        "space weapons": b["outfit space: weapons"], "space engines": b["outfit space: engines"],
        "space other": b["outfit space: other"], "weapon capacity used": b["weapon capacity used"],
        "engine capacity used": b["engine capacity used"],
    }


def run(args) -> None:
    store = Store(args.home)
    game, settings = store.load_catalog(), store.load_settings()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tweaks = {"off": [False], "on": [True], "both": [False, True]}[args.tweaks]
    references = args.references.split(",") if args.references else REFERENCES
    combines = args.combines.split(",") if args.combines else COMBINES
    weights = args.weights.split(",") if args.weights else ["default"]
    plan = [(r, t, ref, comb, wv, h) for r in range(1, args.runs + 1) for t in tweaks for wv in weights
            for ref in references for comb in combines for h in HULLS]
    for i, (rep, tw, ref, comb, wv, hull_name) in enumerate(plan, 1):
        key = f"{hull_name}|{ref}|{comb}|{'tweaks' if tw else 'plain'}|{rep}"
        if wv != "default":
            key = f"{hull_name}|{ref}|{comb}|{'tweaks' if tw else 'plain'}|{wv}|{rep}"
        path = out / (key.replace("|", "__").replace(" ", "_").replace(":", "-") + ".json")
        if path.exists():
            continue
        hull = game.hulls[hull_name]
        emphasize, override = WEIGHTS[wv]
        composites = {**roles.shared_metrics(None), **override}
        if "evasive" in override:
            composites["evasive"] = dict(override["evasive"])
        request = roles.combine([roles.load_role("warship", None)], composites, game, emphasize)
        request.reference, request.combine, request.role.weapon_tweaks = ref, comb, tw
        start = time.monotonic()
        result = solver.optimize(game, hull, request, settings, polish_seconds=args.polish, jobs=args.jobs,
                                 threads=args.threads)
        design = result.design or result.closest
        record = {"key": key, "hull": hull_name, "reference": ref, "combine": comb, "tweaks": tw, "run": rep,
                  "weights": wv,
                  "status": result.status, "seconds": time.monotonic() - start,
                  "score": design.score if design else None, "route": design.route if design else None,
                  "failed": [c.name for c in design.failed] if design else [],
                  "outfits": design.outfits if design else {},
                  "raw": measure(game, hull, design.outfits) if design else None,
                  "stock": measure(game, hull, hull.stock_outfits)}
        path.write_text(json.dumps(record, indent=1))
        print(f"[{i}/{len(plan)}] {key}: {result.status}, score {record['score'] or 0:.3f}, "
              f"{record['seconds']:.0f} s", flush=True)


RATIO_KEYS = ["raw dps", "shield regen", "hull repair", "anti-missile", "turn", "acceleration", "speed"]
SHARE_KEYS = ["space weapons", "space other", "space engines", "weapon capacity used"]
COUNT_KEYS = ["guns", "turrets", "secondary weapons"]


def report(args) -> None:
    records = [json.loads(p.read_text()) for p in sorted(Path(args.out).glob("*.json"))]
    lines = ["# Scoring experiments", "", f"{len(records)} runs. Ratios are design ÷ that hull's stock design "
             "(median of runs); shares are of outfit space or weapon capacity.", ""]
    for hull_name in HULLS:
        rows = [r for r in records if r["hull"] == hull_name and r["raw"]]
        if not rows:
            continue
        stock = rows[0]["stock"]
        lines += [f"## {hull_name}", "",
                  "Stock: " + ", ".join(f"{k} {stock[k]:.3g}" for k in RATIO_KEYS + SHARE_KEYS + COUNT_KEYS), "",
                  "| reference | combine | tweaks | runs | failed | " + " | ".join(RATIO_KEYS + SHARE_KEYS + COUNT_KEYS)
                  + " | route |",
                  "|" + "---|" * (6 + len(RATIO_KEYS) + len(SHARE_KEYS) + len(COUNT_KEYS))]
        groups: dict[tuple, list] = {}
        for r in rows:
            groups.setdefault((r["reference"], r["combine"], r["tweaks"]), []).append(r)
        for (ref, comb, tw), rs in sorted(groups.items(), key=lambda kv: (kv[0][2], REFERENCES.index(kv[0][0]),
                                                                          COMBINES.index(kv[0][1]))):
            med = lambda k: statistics.median(r["raw"][k] for r in rs)
            ratio = lambda k: (f"{med(k) / stock[k]:.2f}" if stock[k] else f"{med(k):.3g} (stock 0)")
            routes = "/".join(sorted({(r["route"] or "").split(": ")[-1] for r in rs}))
            lines.append(f"| {ref} | {comb} | {'on' if tw else 'off'} | {len(rs)} | "
                         f"{sum(1 for r in rs if r['failed'])} | " + " | ".join(ratio(k) for k in RATIO_KEYS) + " | "
                         + " | ".join(f"{med(k):.0%}" for k in SHARE_KEYS) + " | "
                         + " | ".join(f"{med(k):.1f}" for k in COUNT_KEYS) + f" | {routes} |")
        lines.append("")
    Path(args.out, "report.md").write_text("\n".join(lines) + "\n")
    print(f"Wrote {Path(args.out, 'report.md')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--tweaks", choices=["off", "on", "both"], default="both")
    parser.add_argument("--polish", type=float, default=40.0)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--references", help="Comma-separated subset of reference modes.")
    parser.add_argument("--combines", help="Comma-separated subset of combine modes.")
    parser.add_argument("--weights", help="Comma-separated weight variants: " + ", ".join(WEIGHTS))
    parser.add_argument("--report", action="store_true", help="Only write the summary of finished runs.")
    a = parser.parse_args()
    report(a) if a.report else run(a)
