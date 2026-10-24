"""Turn the calibration batch into a report and review sheets.

    python tools/calibrate_report.py      # writes aside/calibration-data.md and aside/review/

Reads experiments/calibration/jobs/*.json and stock.json (see tools/calibrate.py). The written findings and
recommendations live in aside/calibration-report.md (by hand); this file regenerates the data behind them.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments" / "calibration"
ASIDE = ROOT / "aside"
REVIEW = ASIDE / "review"
SUSTAIN = ("Cruising", "Recovery", "Combat", "Weapons in combat", "Interceptor reserves", "Near a bright star")
COMBAT_CATEGORIES = {"Heavy Warship", "Medium Warship", "Light Warship", "Interceptor"}
# Review dimensions: outfit classes they concern, and the probe knobs that move them.
DIMENSIONS = {
    "batteries": (["batteries"], ["FIGHTS", "CRUISE_THRUST", "HEAT_TARGET"]),
    "secondaries": (["secondaries"], ["SECONDARY_SHARE", "MAGAZINE_WINDOW", "FIGHTS"]),
    "heat": (["coolers"], ["HEAT_TARGET", "FIGHTS", "CRUISE_THRUST"]),
    "weapon use": (["guns", "turrets"], ["firepower share", "COMBAT_MIN_SHOTS", "GUN_FULL_AGILITY",
                                         "TURRET_TURN_FULL", "PROJECTILE_SPEED_FULL"]),
    "guns vs turrets": (["guns", "turrets"], ["GUN_FULL_AGILITY", "TURRET_TURN_FULL"]),
    "regeneration": (["shield regen", "hull repair"], ["RECOVERY_LONG", "balance strength"]),
    "mobility": (["engines"], ["CRUISE_THRUST", "balance strength"]),
}


def load_jobs() -> list[dict]:
    jobs = []
    for path in sorted((DATA / "jobs").glob("*.json")):
        try:
            jobs.append(json.loads(path.read_text()))
        except ValueError:
            continue
    return jobs


def pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return values[min(len(values) - 1, int(q * len(values)))]


def fmt(v, kind="pct"):
    if v is None:
        return "—"
    return f"{v:.0%}" if kind == "pct" else f"{v:.3g}"


def table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def job_label(j):
    return f"{j['hull']} — {' + '.join(j['job']['roles'])}"


def sustain_failed(sweep) -> list[str]:
    return [f for f in sweep["failed"] if f.startswith(SUSTAIN)]


def stock_section(stock) -> list[str]:
    ships = stock["ships"]
    lines = ["## Stock ships under the rules", "",
             "Each stock ship with its own loadout, judged by the role for its class (warships: warship or escort;",
             "freighters: freighter; transports and liners: liner; utility: scavenger). Only the energy and heat",
             "rules count here (stock ships don't follow the drive, ramscoop and anti-missile defaults).", ""]
    sweeps = list(next(iter(ships))["sweeps"])
    by_class = defaultdict(list)
    for s in ships:
        by_class[s["category"]].append(s)
    rows = []
    for c, group in sorted(by_class.items()):
        row = [c, len(group)]
        for label in sweeps:
            ok = sum(1 for s in group if not sustain_failed(s["sweeps"][label]))
            row.append(f"{ok / len(group):.0%}")
        rows.append(row)
    lines += ["Share of stock ships passing every energy and heat rule, per tunable setting:", ""]
    lines += table(["class", "ships"] + sweeps, rows)
    # Habits by class
    rows = []
    for c, group in sorted(by_class.items()):
        heat = [s["sweeps"]["baseline"].get("combat heat peak") for s in group]
        rows.append([c, len(group), fmt(statistics.median([s["weapon capacity used"] for s in group])),
                     f"{sum(1 for s in group if s['batteries'] > 0) / len(group):.0%}",
                     f"{sum(1 for s in group if s['secondaries'] > 0) / len(group):.0%}",
                     fmt(pct(heat, 0.5)), fmt(pct(heat, 0.9))])
    lines += ["Stock habits by class:", ""]
    lines += table(["class", "ships", "weapon capacity used (median)", "with batteries", "with secondaries",
                    "combat heat peak median", "p90"], rows)
    # By faction for warships
    rows = []
    by_source = defaultdict(list)
    for s in ships:
        if s["category"] in COMBAT_CATEGORIES:
            by_source[s["source"]].append(s)
    for src, group in sorted(by_source.items(), key=lambda kv: -len(kv[1])):
        if len(group) < 3:
            continue
        heat = [s["sweeps"]["baseline"].get("combat heat peak") for s in group]
        fails = Counter(f.split(":")[0] for s in group for f in sustain_failed(s["sweeps"]["baseline"]))
        rows.append([src, len(group), fmt(statistics.median([s["weapon capacity used"] for s in group])),
                     f"{sum(1 for s in group if s['batteries'] > 0) / len(group):.0%}",
                     f"{sum(1 for s in group if s['secondaries'] > 0) / len(group):.0%}",
                     fmt(pct(heat, 0.5)), fmt(pct(heat, 0.9)),
                     ", ".join(f"{k} {v}" for k, v in fails.most_common(2))])
    lines += ["Warships and interceptors by faction (source group): faction flavours, not norms.", ""]
    lines += table(["faction", "ships", "weapon capacity used", "batteries", "secondaries", "heat peak median",
                    "p90", "most failed rules"], rows)
    return lines


def runs_section(jobs) -> list[str]:
    lines = ["## Optimizer designs", ""]
    status = Counter(j["status"] for j in jobs)
    lines += [f"{len(jobs)} runs: " + ", ".join(f"{v} {k}" for k, v in status.most_common()) + ".", ""]
    done = [j for j in jobs if j.get("design")]
    by_class = defaultdict(list)
    for j in done:
        by_class[j["category"]].append(j)
    rows = []
    for c, group in sorted(by_class.items()):
        d = [j["design"] for j in group]
        rows.append([c, len(group), fmt(statistics.median(x["balance"]["weapon capacity used"] for x in d)),
                     fmt(statistics.median(x["balance"]["engine capacity used"] for x in d)),
                     f"{sum(1 for x in d if x['usage']['batteries']['count'] > 0) / len(d):.0%}",
                     f"{sum(1 for x in d if x['usage']['secondaries']['count'] > 0) / len(d):.0%}",
                     fmt(pct([x.get('combat heat peak') for x in d], 0.5)),
                     fmt(pct([x.get('combat battery drawdown') for x in d], 0.5))])
    lines += table(["class", "designs", "weapon capacity used", "engine capacity used", "with batteries",
                    "with secondaries", "combat heat peak", "battery drawdown"], rows)
    capped = [j["capped solves"] / j["solver runs"] for j in jobs if j.get("solver runs")]
    if capped:
        lines += [f"Search: {statistics.mean(capped):.0%} of solver runs hit their time limit on average.", ""]
    return lines


def class_section(jobs) -> list[str]:
    lines = ["## Why each class was or wasn't used (class report)", "",
             "For each design, the best outfits of an unused class were forced in (or one more of a used class),",
             "room made, and the design re-polished. Score change is against the design as found; negative means",
             "the class costs more than it adds under the current numbers.", ""]
    rows_by_class = defaultdict(list)
    for j in jobs:
        for r in j.get("class report", []):
            rows_by_class[r["class"]].append((j, r))
    rows = []
    for cls, items in rows_by_class.items():
        changes = [r["score change"] for _, r in items if r["score change"] is not None]
        reasons = Counter(r["reason"].split(":")[0] for _, r in items)
        rows.append([cls, len(items), sum(1 for _, r in items if not r["used"]),
                     fmt(statistics.median(changes), "num") if changes else "—",
                     sum(1 for _, r in items if r["reason"].startswith("better")),
                     "; ".join(f"{k} ({v})" for k, v in reasons.most_common(3))])
    lines += table(["class", "tries", "unused in design", "median score change", "search missed it", "reasons"],
                   sorted(rows))
    misses = [(j, r) for cls in rows_by_class for j, r in rows_by_class[cls] if r["reason"].startswith("better")]
    if misses:
        lines += ["Search misses (forcing it in scored higher):", ""]
        lines += [f"- {job_label(j)}: {r['outfit']} ({r['class']}) +{r['score change']:.3f}" for j, r in misses]
        lines += [""]
    return lines


def probe_section(jobs) -> list[str]:
    lines = ["## Tipping points (probes)", "",
             "On the probe hulls, each tunable was changed alone and the design re-polished from the baseline.",
             "Columns count hulls where the change happened.", ""]
    rows = []
    knobs = defaultdict(list)
    for j in jobs:
        base = j.get("design")
        for p in j.get("probes", []):
            if base and p.get("design"):
                knobs[(p["knob"], json.dumps(p["value"]))].append((base, p))
    for (knob, value), items in sorted(knobs.items()):
        bat = sum(1 for b, p in items if b["usage"]["batteries"]["count"] == 0 < p["design"]["usage"]["batteries"]["count"])
        sec = sum(1 for b, p in items if b["usage"]["secondaries"]["count"] == 0 < p["design"]["usage"]["secondaries"]["count"])
        wcu = [p["design"]["balance"]["weapon capacity used"] - b["balance"]["weapon capacity used"] for b, p in items]
        heat = [(p["design"].get("combat heat peak") or 0) - (b.get("combat heat peak") or 0) for b, p in items
                if b.get("combat heat peak") is not None]
        fails = sum(1 for _, p in items if not p.get("baseline passes", True))
        rows.append([knob, value, len(items), bat, sec, f"{statistics.mean(wcu):+.0%}" if wcu else "—",
                     f"{statistics.mean(heat):+.0%}" if heat else "—", fails])
    lines += table(["knob", "value", "hulls", "batteries appear", "secondaries appear", "weapon capacity used",
                    "combat heat peak", "baseline fails the rules"], rows)
    return lines


def variants_section(jobs) -> list[str]:
    """Phase 2: full re-solves under alternative settings, against the same hull's baseline."""
    lines = ["## Full re-solves under alternative settings (phase 2)", "",
             "Each row is a complete new optimization of the same hull and role with one group of settings changed.",
             "Deltas are against that hull's baseline design.", ""]
    base = {(j["hull"], tuple(j["job"]["roles"])): j for j in jobs if not j["job"].get("variant")}
    rows_by_variant = defaultdict(list)
    for j in jobs:
        v = j["job"].get("variant")
        b = base.get((j["hull"], tuple(j["job"]["roles"])))
        if not v or not b or not b.get("design") or not j.get("design"):
            continue
        rows_by_variant[v].append((b["design"], j["design"], j["hull"]))
    summary = []
    for v, items in sorted(rows_by_variant.items()):
        wcu = [d["balance"]["weapon capacity used"] - b["balance"]["weapon capacity used"] for b, d, _ in items]
        ecu = [d["balance"]["engine capacity used"] - b["balance"]["engine capacity used"] for b, d, _ in items]
        bat = sum(1 for b, d, _ in items if d["usage"]["batteries"]["count"] > b["usage"]["batteries"]["count"])
        sec = sum(1 for b, d, _ in items if d["usage"]["secondaries"]["count"] > b["usage"]["secondaries"]["count"])
        heat = [(d.get("combat heat peak") or 0) - (b.get("combat heat peak") or 0) for b, d, _ in items
                if b.get("combat heat peak") is not None and d.get("combat heat peak") is not None]
        draw = [(d.get("combat battery drawdown") or 0) - (b.get("combat battery drawdown") or 0) for b, d, _ in items
                if b.get("combat battery drawdown") is not None and d.get("combat battery drawdown") is not None]
        summary.append([v, len(items), f"{statistics.mean(wcu):+.0%}", f"{statistics.mean(ecu):+.0%}", bat, sec,
                        f"{statistics.mean(heat):+.0%}" if heat else "—", f"{statistics.mean(draw):+.0%}" if draw else "—"])
    lines += table(["variant", "hulls", "weapon capacity used", "engine capacity used", "more batteries",
                    "more secondaries", "combat heat peak", "battery drawdown"], summary)
    detail = []
    for v, items in sorted(rows_by_variant.items()):
        for b, d, hull in items:
            detail.append([v, hull, f"{b['balance']['weapon capacity used']:.0%} → {d['balance']['weapon capacity used']:.0%}",
                           f"{b['usage']['batteries']['count']} → {d['usage']['batteries']['count']}",
                           f"{b['usage']['secondaries']['count']} → {d['usage']['secondaries']['count']}",
                           f"{fmt(b.get('combat heat peak'))} → {fmt(d.get('combat heat peak'))}",
                           f"{b['route'] or '—'} → {d['route'] or '—'}"])
    lines += ["Per hull:", ""]
    lines += table(["variant", "hull", "weapon capacity used", "batteries", "secondaries", "combat heat peak",
                    "route"], detail)
    return lines


def design_block(game_free_design: dict, title: str) -> list[str]:
    d = game_free_design
    lines = [f"**{title}** — score {d['score']:.3f}" + (f", route {d['route']}" if d.get("route") else "")
             + (f", FAILS {', '.join(d['failed'])}" if d.get("failed") else ""), ""]
    b = d["balance"]
    lines.append(f"weapon capacity {b['weapon capacity used']:.0%}, engine capacity {b['engine capacity used']:.0%}, "
                 f"batteries {d['usage']['batteries']['count']} (+{d['battery capacity added']:.0f} energy capacity), secondaries {d['usage']['secondaries']['count']}, "
                 f"combat heat peak {fmt(d.get('combat heat peak'))}, battery drawdown "
                 f"{fmt(d.get('combat battery drawdown'))}, agility {d['agility']:.0f}")
    lines += ["", "```"] + [f"{c:4} × {n}" for n, c in d["outfits"].items()] + ["```", "",
                                                                              "Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:", ""]
    return lines


def hull_sheet(hull: str, jobs: list[dict]) -> list[str]:
    lines = [f"# {hull}", ""]
    for j in jobs:
        variant = j["job"].get("variant")
        lines += [f"## {' + '.join(j['job']['roles'])}" + (f" — variant: {variant}" if variant else "")
                  + f" ({j['status']})", ""]
        if not j.get("design"):
            lines += [f"No design: {', '.join(j.get('blockers') or [])}", ""]
            continue
        lines += design_block(j["design"], "Baseline (current numbers)")
        if j.get("metrics"):
            lines += ["Score breakdown:", ""]
            lines += table(["metric", "weight", "balance weight", "score", "standing"],
                           [[m["metric"], f"{m['weight']:+.2f}", f"{m['balance weight']:+.2f}", fmt(m["score"], "num"),
                             "; ".join(m["standing"].values())] for m in j["metrics"]])
        if j.get("class report"):
            lines += ["Why each class is or isn't used:", ""]
            lines += table(["class", "outfit", "tried", "score change", "reason", "displaced"],
                           [[r["class"], r["outfit"], r["kind"], fmt(r["score change"], "num"), r["reason"],
                             ", ".join(r["displaced"])] for r in j["class report"]])
        for dim, (_, knobs) in DIMENSIONS.items():
            probes = [p for p in j.get("probes", []) if p["knob"] in knobs and p.get("design")]
            if not probes:
                continue
            lines += [f"### Sweep: {dim}", ""]
            for p in probes:
                lines += design_block(p["design"], f"{p['knob']} = {json.dumps(p['value'])}")
    return lines


def dimension_sheet(dim: str, jobs: list[dict]) -> list[str]:
    classes, knobs = DIMENSIONS[dim]
    lines = [f"# Drill-down: {dim}", "",
             "Hulls worth looking at for this dimension, most informative first: nearest a tipping point (forcing",
             "the class in costs least, or the search missed it), then where the class is used heavily.", ""]
    scored = []
    for j in jobs:
        rows = [r for r in j.get("class report", []) if r["class"] in classes and r["score change"] is not None]
        if not rows:
            continue
        best = max(r["score change"] for r in rows)
        scored.append((-best, job_label(j), j, best, rows))
    scored.sort(key=lambda t: t[0])
    table_rows = []
    for _, label, j, best, rows in scored[:20]:
        r = max(rows, key=lambda x: x["score change"])
        table_rows.append([f"[{label}](hulls/{_safe(j['hull'])}.md)", r["outfit"], f"{best:+.3f}", r["reason"]])
    lines += table(["design", "outfit tried", "score change", "reason"], table_rows)
    return lines


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-+_." else "_" for c in name)


def main() -> int:
    jobs = load_jobs()
    stock = json.loads((DATA / "stock.json").read_text()) if (DATA / "stock.json").exists() else None
    lines = ["# Calibration data", "", "Generated by tools/calibrate_report.py from experiments/calibration/. The",
             "findings and recommendations are in aside/calibration-report.md.", ""]
    base_jobs = [j for j in jobs if not j["job"].get("variant")]
    lines += runs_section(base_jobs) + class_section(base_jobs) + probe_section(base_jobs) + variants_section(jobs)
    if stock:
        lines += stock_section(stock)
    (ASIDE / "calibration-data.md").write_text("\n".join(lines) + "\n")
    (REVIEW / "hulls").mkdir(parents=True, exist_ok=True)
    (REVIEW / "dimensions").mkdir(parents=True, exist_ok=True)
    by_hull = defaultdict(list)
    for j in jobs:
        by_hull[j["hull"]].append(j)
    for hull, group in by_hull.items():
        (REVIEW / "hulls" / f"{_safe(hull)}.md").write_text("\n".join(hull_sheet(hull, group)) + "\n")
    for dim in DIMENSIONS:
        (REVIEW / "dimensions" / f"{_safe(dim)}.md").write_text(
            "\n".join(dimension_sheet(dim, jobs)).replace("](hulls/", "](../hulls/") + "\n")
    # Starting set: per class, the hull with the most finished designs (variants count, so the probe hulls with
    # phase-2 re-solves come first).
    finished = Counter(j["hull"] for j in jobs if j.get("design"))
    best_per_class: dict[str, str] = {}
    for j in jobs:
        if finished[j["hull"]] and (j["category"] not in best_per_class
                                    or finished[j["hull"]] > finished[best_per_class[j["category"]]]):
            best_per_class[j["category"]] = j["hull"]
    probe_hulls = sorted(set(best_per_class.values()) | {j["hull"] for j in jobs
                                                         if j["job"].get("variant") and j.get("design")})
    index = ["# Review sheets", "",
             "Start with these hulls (each class represented). Each sheet has the baseline design per role, why",
             "each class of outfit is or isn't used, and sweeps where one group of numbers changes at a time. Mark",
             "designs that look right and, after testing, play right.", ""]
    index += [f"- [{h}](hulls/{_safe(h)}.md)" for h in probe_hulls]
    index += ["", "Drill down by dimension (ranked lists of other hulls):", ""]
    index += [f"- [{d}](dimensions/{_safe(d)}.md)" for d in DIMENSIONS]
    index += ["", "All hulls:", ""] + [f"- [{h}](hulls/{_safe(h)}.md)" for h in sorted(by_hull)]
    (REVIEW / "index.md").write_text("\n".join(index) + "\n")
    print(f"{len(jobs)} jobs -> aside/calibration-data.md, aside/review/ ({len(by_hull)} hull sheets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
