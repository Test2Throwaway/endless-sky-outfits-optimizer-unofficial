"""Visibility for calibration: what a design is made of, why each class of outfit was or wasn't used, and how the
design changes when a tunable number changes.

- `record`: a run as a JSON-able dict (design, metrics with scores and weights, checks, binding limits, class usage,
  search diagnostics, the tunables in force).
- `class_report`: for each outfit class (batteries, secondaries, guns, …), force the best outfits of an unused class
  in (or one more of a used class), re-polish, and report the score change, what it displaced and why.
- `probe`: re-polish a design with tunables overridden, and report how its class usage and score change.
"""

from __future__ import annotations

import math
import re

from . import calculator, roles, solver, tuning
from .gamedata import GameData, Outfit

CLASSES = ["batteries", "generators", "coolers", "shield regen", "hull repair", "engines", "guns", "turrets",
           "secondaries", "anti-missile", "utility weapons", "ammunition", "expansions", "other"]


def outfit_class(outfit: Outfit) -> str:
    a, w = outfit.attributes, outfit.weapon
    if w is not None:
        s = w.stats
        if s.get("anti-missile"):
            return "anti-missile"
        damage = s.get("shield damage", 0) + s.get("hull damage", 0) or bool(w.submunitions)
        if not damage:
            return "utility weapons"
        if outfit.category == "Secondary Weapons":
            return "secondaries"
        return "turrets" if a.get("turret mounts", 0) < 0 else "guns"
    if outfit.category == "Ammunition":
        return "ammunition"
    if a.get("engine capacity", 0) < 0 or a.get("thrust") or a.get("turn") or a.get("reverse thrust"):
        return "engines"
    if a.get("energy generation", 0) > 0 or a.get("solar collection", 0) > 0 or a.get("fuel energy", 0) > 0:
        return "generators"
    if a.get("energy capacity", 0) > 0:
        return "batteries"
    if a.get("cooling", 0) > 0 or a.get("active cooling", 0) > 0 or a.get("heat dissipation", 0) > 0:
        return "coolers"
    if a.get("shield generation", 0) > 0 or a.get("delayed shield generation", 0) > 0:
        return "shield regen"
    if a.get("hull repair rate", 0) > 0 or a.get("delayed hull repair rate", 0) > 0:
        return "hull repair"
    if a.get("cargo space", 0) > 0 or a.get("outfit space", 0) > 0:
        return "expansions"
    return "other"


def _space(outfit: Outfit) -> float:
    return max(1.0, -outfit.attributes.get("outfit space", 0.0))


def class_strength(game: GameData, outfit: Outfit) -> float:
    """A rough per-space strength used to pick which outfits of a class to try first."""
    a, cls = outfit.attributes, outfit_class(outfit)
    if outfit.weapon is not None:
        w = calculator._weapon_stats(game, outfit, 1)
        value = w.shield_damage + w.hull_damage or w.anti_missile or abs(w.hit_force) or w.tractor
        return value / max(1.0, -a.get("weapon capacity", 0.0) or _space(outfit))
    key = {"batteries": "energy capacity", "generators": "energy generation", "coolers": "cooling",
           "shield regen": "shield generation", "hull repair": "hull repair rate", "engines": "thrust",
           "expansions": "cargo space"}.get(cls)
    value = a.get(key, 0.0) if key else 0.0
    if cls == "coolers":
        value = a.get("cooling", 0) + a.get("active cooling", 0) + 10 * a.get("heat dissipation", 0)
    return value / _space(outfit)


def usage(game: GameData, outfits: dict[str, int]) -> dict[str, dict]:
    out = {c: {"count": 0, "outfit space": 0.0, "outfits": {}} for c in CLASSES}
    for name, count in outfits.items():
        o = game.outfits[name]
        row = out[outfit_class(o)]
        row["count"] += count
        row["outfit space"] += -min(0.0, o.attributes.get("outfit space", 0.0)) * count
        row["outfits"][name] = count
    return out


_PATTERNS = {
    "heat peak": re.compile(r"peaks at (\d+)% of max heat"),
    "settles": re.compile(r"settles at (\d+)% of max heat"),
    "energy low": re.compile(r"lowest stored energy (-?\d+) of (\d+)"),
}


def check_numbers(checks) -> dict:
    """Numbers worth tracking from the check details: combat heat peak, lowest stored energy, cruising heat."""
    out = {}
    for c in checks:
        if c.name.startswith("Combat"):
            if (m := _PATTERNS["heat peak"].search(c.detail)):
                out["combat heat peak"] = int(m.group(1)) / 100
            if (m := _PATTERNS["energy low"].search(c.detail)):
                low, cap = int(m.group(1)), int(m.group(2))
                out["combat energy low"] = low
                out["combat battery drawdown"] = 1 - low / cap if cap else 0.0
        elif c.name == "Cruising: heat" and (m := _PATTERNS["settles"].search(c.detail)):
            out["cruise heat"] = int(m.group(1)) / 100
        elif c.name.startswith("Recovery") and (m := _PATTERNS["heat peak"].search(c.detail) or
                                                 re.search(r"peak heat (\d+)%", c.detail)):
            out["recovery heat peak"] = int(m.group(1)) / 100
    return out


def design_summary(game: GameData, design, request) -> dict:
    ship = design.ship
    b = solver.balance(game, ship)
    hull_energy = ship.hull.attributes.get("energy capacity", 0.0)
    u = usage(game, design.outfits)
    return {
        "score": design.score, "route": design.route, "failed": [c.name for c in design.failed],
        "outfits": dict(sorted(design.outfits.items())),
        "balance": b,
        "battery capacity added": ship.get("energy capacity") - hull_energy,
        "secondary share": roles.metric_value(ship, request.role, "secondary share"),
        "agility": ship.agility, "mass": ship.mass,
        "usage": {c: {"count": v["count"], "outfit space": v["outfit space"]} for c, v in u.items()},
        **check_numbers(design.checks),
    }


def metric_rows(design, request, scales) -> list[dict]:
    scorer = solver.Scorer(request, scales)
    routes = request.routes or [roles.Route("", request.weights)]
    route = next((r for r in routes if r.label == design.route), routes[0])
    terms = {n: t for n in route.weights if (t := scorer.term(n, design.metrics)) is not None}
    marginal = scorer.marginal_weights(route.weights, design.metrics)
    rows = []
    for name, weight in sorted(route.weights.items(), key=lambda kv: -abs(kv[1])):
        parts = request.products.get(name, {name: 1.0})
        rows.append({
            "metric": name, "weight": weight, "score": terms.get(name),
            "balance weight": marginal.get(name, weight),
            "contribution": weight * terms[name] if name in terms else None,
            "values": {m: design.metrics.get(m) for m in parts},
            "standing": {m: scales[m].describe(design.metrics[m]) for m in parts if m in scales},
        })
    return rows


def record(game: GameData, hull, request, result, extra: dict | None = None) -> dict:
    design = result.design or result.closest
    out = {
        "hull": hull.name, "category": hull.category, "roles": [r.name for r in request.roles],
        "status": result.status, "blockers": result.blockers,
        "tuning": tuning.snapshot(), "balance strength": request.balance, "reference": request.reference,
        "seconds": result.seconds, "solver runs": result.iterations, "capped solves": result.capped_solves,
        "polish moves": result.polish_moves, "candidates": result.candidates,
        "starts": [{"start": s, "score": v} for s, v in result.starts],
        **(extra or {}),
    }
    if design is not None:
        out["design"] = design_summary(game, design, request)
        out["metrics"] = metric_rows(design, request, result.scales)
        out["checks"] = [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in design.checks]
    return out


def _locked_judge(judge, name: str, count: int):
    """A judge that fails any design with fewer than `count` of `name` (so polish keeps the forced outfit)."""
    def locked(outfits: dict[str, int], ship=None):
        design = judge(outfits, ship)
        if outfits.get(name, 0) < count:
            design.checks.append(calculator.Check(f"Forced: {name}", False, "removed"))
        return design
    return locked


REPAIR_CLASSES = ("coolers", "generators", "batteries", "shield regen", "hull repair", "engines", "expansions")
REPAIR_PER_CLASS = 6


def repair_options(game: GameData, pool: list[Outfit], keep: str) -> list[str]:
    """Outfits a repair may add: the forced weapon's ammunition, and the strongest few of the support classes."""
    names = []
    forced = game.outfits[keep]
    if forced.weapon is not None and forced.weapon.ammo:
        names.append(forced.weapon.ammo[0])
    by_class: dict[str, list[Outfit]] = {}
    for o in pool:
        by_class.setdefault(outfit_class(o), []).append(o)
    for cls in REPAIR_CLASSES:
        names += [o.name for o in sorted(by_class.get(cls, []), key=lambda o: -class_strength(game, o))
                  [:REPAIR_PER_CLASS]]
    pool_names = {o.name for o in pool}
    return [n for n in dict.fromkeys(names) if n in pool_names]


def _violation(design) -> tuple:
    """How far a design is from passing: failing checks other than the fit rule, then the capacity deficit (the
    amount by which capacities like outfit space are overdrawn), then the score."""
    others = sum(1 for c in design.failed if not c.name.startswith(("Fits", "Magazine")))
    deficit = sum(-v for k, v in design.ship.attributes.items()
                  if v < 0 and calculator.MINIMUMS.get(k, 0.0) == 0.0 and k != "required crew")
    for c in design.failed:
        if c.name.startswith("Magazine") and (m := re.search(r"carries (\d+), needs (\d+)", c.detail)):
            deficit += int(m.group(2)) - int(m.group(1))
    return (others, deficit, -design.score)


def repair(judge, outfits: dict[str, int], keep: str, additions: list[str] = (), bounds: dict | None = None,
           steps: int = 30):
    """Make a design with a forced outfit pass: repeatedly take out one outfit (not the forced one) or add one of
    `additions`, whichever leaves the fewest failing checks, then the best score. Returns the design (possibly still
    failing)."""
    design = judge(outfits)
    for _ in range(steps):
        if not design.failed:
            break
        options = []
        for name, count in design.outfits.items():
            if name != keep:
                trial = {**design.outfits, name: count - 1}
                options.append(judge({n: c for n, c in trial.items() if c}))
        for name in additions:
            if bounds is not None and design.outfits.get(name, 0) >= bounds.get(name, 0):
                continue
            options.append(judge({**design.outfits, name: design.outfits.get(name, 0) + 1}))
        if not options:
            break
        best = min(options, key=_violation)
        if _violation(best) >= _violation(design):
            break
        design = best
    return design


def _reason(forced, polished, base) -> str:
    if polished is None or polished.failed:
        names = [c.name for c in (polished or forced).failed if not c.name.startswith("Forced")]
        return "can't pass: " + ", ".join(names[:3]) if names else "can't pass"
    if polished.score > base.score + 1e-6:
        return "better: the search missed it"
    first = [c.name for c in forced.failed]
    if any(n.startswith("Fits") for n in first):
        return "no room as is (fit), worth less than what it displaces"
    if first:
        return "breaks " + ", ".join(first[:2]) + " as is; worth less after making room"
    return "fits, but worth less than what it displaces"


def class_report(result, seconds: float = 6.0, per_class: int = 2) -> list[dict]:
    """Force outfits of each class into the result's design and re-polish (see module docstring)."""
    ctx = result.context
    base = result.design
    if ctx is None or base is None:
        return []
    game, hull, pool, bounds = ctx.game, ctx.hull, ctx.pool, ctx.bounds
    judge = ctx.judge()
    by_class: dict[str, list[Outfit]] = {}
    for o in pool:
        by_class.setdefault(outfit_class(o), []).append(o)
    rows = []
    for cls in CLASSES:
        members = by_class.get(cls, [])
        if not members or cls in ("ammunition", "other"):
            continue
        used = {n: c for n, c in base.outfits.items() if outfit_class(game.outfits[n]) == cls}
        if used:
            name = max(used, key=used.get)
            tries = [(name, used[name] + 1, "one more")]
        else:
            ranked = sorted(members, key=lambda o: -class_strength(game, o))[:per_class]
            tries = [(o.name, 1, "forced in") for o in ranked]
        for name, count, kind in tries:
            if bounds.get(name, 0) < count:
                continue
            outfits = {**base.outfits, name: count}
            forced = judge(outfits)
            locked = _locked_judge(judge, name, count)
            repaired = repair(locked, outfits, name, repair_options(game, pool, name), bounds)
            polished, _ = solver.polish(game, hull, pool, bounds, repaired, locked, seconds) \
                if not repaired.failed else (repaired, 0)
            removed = {n: c - polished.outfits.get(n, 0) for n, c in base.outfits.items()
                       if polished.outfits.get(n, 0) < c and n != name}
            rows.append({
                "class": cls, "used": bool(used), "outfit": name, "kind": kind,
                "score change": (polished.score - base.score) if not polished.failed else None,
                "as is fails": [c.name for c in forced.failed],
                "displaced": removed, "reason": _reason(forced, polished, base),
            })
    return rows


def probe(result, overrides: dict, seconds: float = 10.0) -> dict:
    """Re-polish the result's design with tunables overridden: does the design keep passing, and what changes?"""
    ctx = result.context
    base = result.design
    if ctx is None or base is None:
        return {}
    with tuning.override(overrides):
        scales = solver.reference_scales(ctx.game, ctx.request, ctx.request.metrics, hull=ctx.hull)
        scales.update({m: s for m, s in ctx.scales.items() if m not in scales})
        scorer = solver.Scorer(ctx.request, scales)
        judge = lambda outfits, ship=None: solver.evaluate_design(ctx.game, ctx.hull, outfits, ctx.request, scorer,
                                                                  ctx.disruption, ctx.capture_targets, ship)
        start = judge(base.outfits)
        polished, moves = solver.polish(ctx.game, ctx.hull, ctx.pool, ctx.bounds, start, judge, seconds)
        summary = design_summary(ctx.game, polished, ctx.request)
    return {"overrides": overrides, "baseline passes": not start.failed,
            "baseline fails": [c.name for c in start.failed], "moves": moves, "design": summary}


def search_misses(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["reason"].startswith("better")]
