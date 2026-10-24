"""Optimizer: choose outfit counts for one hull that best fit a design request.

Method (see docs/design-notes.md):

- One integer count per candidate outfit, solved with OR-Tools CP-SAT.
- The game's fit rule and the energy and heat scenarios are linear constraints. Values that depend on the
  design itself (mass in acceleration, agility in weapon value, ...) are linearized around the current design
  and re-solved, inside a mass band (a trust region) that shrinks when a step doesn't improve the exact score.
- Every design the solver returns is re-checked with the calculator, which matches the game. A design that
  fails a hard check is excluded and the solver tries again.
- Each weighted metric is scored against the stock ships of the game: its place in their distribution, so 0.5
  is a typical stock ship and 1 the best one (absolute scoring). Metrics too few stock ships have fall back to
  the best this hull reaches for that metric alone.
- Several starts, like a person designing by hand: every route of the "best of" composites, and weapon and
  engine budgets (the share of weapon and engine capacity those outfits may take) spread over the role's ranges.
  The best design by exact score is then polished by trying every single add, remove and swap.
- If no design exists, each requirement group is switched off in turn to find what blocks it.
"""

from __future__ import annotations

import bisect
import concurrent.futures
import math
import multiprocessing
import os
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from . import calculator, roles
from .availability import Availability, source_group
from .calculator import Check, Role, Ship
from .gamedata import GameData, Hull, Outfit
from .storage import Settings

SCALE = 10_000            # attributes have 4 decimal places in the game
OBJECTIVE_SCALE = 1_000_000
# Never used in designs: hand-to-hand gear gets no weight (illegal-boarding roles will add Nerve Gas, one per
# bunk, separately), and licences and minerals aren't installable.
NOT_INSTALLABLE = ("Licenses", "Minerals", "Hand to Hand")
# Absolute scoring: a metric needs this many stock ships with a non-zero value to be scored against them.
REFERENCE_MIN_SHIPS = 5
# Above the best stock ship, each further 100% of its value adds this much score (diminishing, never flat).
TAIL_SLOPE = 0.5
# Which stock ships a design is scored against (experiment: see docs/experiments.md).
#   legacy: every stock ship (the original rule); all: every stock ship outside EXCLUDED_CATEGORIES;
#   family: ships of the hull's class family (light to heavy warships, ...); class: the hull's own category;
#   stock: improvement over this hull's stock design, log2(1 + value / stock value) / 2 (stock = 0.5, 3x = 1,
#   7x = 1.5), falling back to `family` where the stock design has none of the metric.
REFERENCE_MODES = ("legacy", "all", "family", "class", "stock")
# Never part of a reference: size outliers and ships that aren't really ships (user's class notes).
EXCLUDED_CATEGORIES = {"Superheavy", "Unclassified", "Unclassified Minor", "Game Mechanics", ""}
CLASS_FAMILIES = [{"Light Warship", "Medium Warship", "Heavy Warship"}, {"Light Freighter", "Heavy Freighter"},
                  {"Transport", "Space Liner"}, {"Interceptor", "Fighter", "Drone"}, {"Utility"}]
# How metric scores combine in a route (experiment): sum (weighted sum, the original rule), or a weighted power mean
# that penalizes lopsided designs: "power:0.5", "power:0" (geometric mean). Negative weights stay a plain sum.
COMBINE_MODES = ("sum", "power:0.5", "power:0")
COMBINE_FLOOR = 0.01             # a metric score is never taken below this in a power mean
# Trust region: the mass of the next design stays within this share of the current one; halves on a step that
# doesn't improve the exact score, widens on one that does.
MASS_BAND = 0.5
MIN_MASS_BAND = 0.05
# Starting designs per budget range (two when the range is narrow).
BUDGET_STEPS = 3
# Tie-break: score lost per unit of outfit space or cargo space an outfit uses up, plus one unit per outfit fitted.
# Far below any real gain, so it only decides between designs that are otherwise equal: no outfits that do nothing
# (including ones that take no space, like ammunition for a weapon that isn't fitted), and the space-efficient way
# to get the same result (the passive cooling ladder: a Large Heat Shunt before several small ones).
WASTE_PENALTY = 1e-5
# Reverse thrust on ships whose roles don't ask for it (user): with reverse thrusters, "reverse" fires them instead of
# flipping the ship to brake with the main engines. Too little reverse thrust (roles.reverse_level "useless": it stops
# the ship more slowly than flipping would) is worse than none; anything more is a very small plus.
REVERSE_USELESS_PENALTY = 0.02
REVERSE_BONUS = 0.005
# Polish the best few starting designs (more time each beats a little time for all); with more parallel jobs,
# as many as there are jobs.
POLISH_DESIGNS = 4
# Parallelism: starting designs run in this many worker processes, each solve using this many CP-SAT threads.
# By default both come from the CPUs this process may use (see plan_parallelism).
THREADS_PER_JOB = 2
MAX_SOLVER_THREADS = 16      # CP-SAT gains little beyond this for one solve


def available_cpus() -> int:
    """Logical CPUs this process may use (respects container and affinity limits where the OS reports them)."""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:          # Windows, macOS
        return max(1, os.cpu_count() or 1)


def plan_parallelism(starts: int, jobs: int | None = None, threads: int | None = None) -> tuple[int, int]:
    """(worker processes, CP-SAT threads per solve). Defaults: two threads per job, as many jobs as fit, at most one
    per start. A Ryzen 9 3900X (24 threads) runs 12 starts at once; a 4-CPU container runs 2."""
    cpus = available_cpus()
    if jobs is None:
        jobs = max(1, min(starts, cpus // (threads or THREADS_PER_JOB)))
    jobs = max(1, min(jobs, starts))
    if threads is None:
        threads = max(1, min(MAX_SOLVER_THREADS, cpus // jobs))
    return jobs, threads


_threads = min(8, available_cpus())     # CP-SAT threads per solve in this process


@dataclass
class Scale:
    """How one metric is scored: against stock ships (sorted positive values), or against `ideal`."""
    values: list[float] = field(default_factory=list)
    ideal: float | None = None

    def score(self, v: float) -> float:
        if self.ideal is not None:
            return v / self.ideal
        q, n = self.values, len(self.values)
        if v <= 0:
            return v / q[0] / n
        if v >= q[-1]:
            return 1 + TAIL_SLOPE * (v - q[-1]) / q[-1]
        i = bisect.bisect_right(q, v)            # q[i-1] <= v < q[i]
        lo_v, lo_p = (q[i - 1], i / n) if i else (0.0, 0.0)
        hi_v, hi_p = q[i], (i + 1) / n
        return lo_p + (hi_p - lo_p) * (v - lo_v) / (hi_v - lo_v) if hi_v > lo_v else hi_p

    def slope(self, v: float) -> float:
        """Secant slope around v: smooth enough to linearize the stepped distribution."""
        width = max(0.25 * abs(v), self.ideal * 0.25 if self.ideal is not None else self.values[0])
        lo = max(0.0, v - width) if v >= 0 else v - width
        return (self.score(v + width) - self.score(lo)) / (v + width - lo)

    def describe(self, v: float) -> str:
        if self.ideal is not None:
            return f"{v / self.ideal:.0%} of this hull's best"
        better = bisect.bisect_left(self.values, v) if v > 0 else 0
        return f"beats {better} of {len(self.values)} stock ships"


@dataclass
class StockScale:
    """Improvement over the hull's stock design: log2(1 + value / stock) / 2. Diminishing returns: every doubling
    of an already large improvement adds about the same score."""
    stock: float

    def score(self, v: float) -> float:
        return math.log2(1 + max(v, 0.0) / self.stock) / 2 if v >= 0 else v / self.stock / 2

    def slope(self, v: float) -> float:
        return 1 / (2 * math.log(2) * (self.stock + max(v, 0.0)))

    def describe(self, v: float) -> str:
        return f"{v / self.stock:.2f}x this hull's stock design"


def _family(category: str) -> set[str]:
    return next((f for f in CLASS_FAMILIES if category in f), {category})


def reference_weapons(game: GameData, settings: Settings) -> tuple:
    """Every damage weapon the player can get, for weapon value's average (see calculator.average_suitability)."""
    available = Availability(game, settings)
    stats = [calculator._weapon_stats(game, o, 1) for o in game.outfits.values()
             if o.weapon is not None and o.category and o.category not in NOT_INSTALLABLE and available.outfit_ok(o)]
    return tuple(w for w in stats if w.offensive)


def stock_agility(game: GameData) -> dict[str, float]:
    """Every hull's and variant's agility with its stock outfits (where they fit)."""
    out = {}
    for hull in list(game.hulls.values()) + list(game.variants.values()):
        if hull.stock_outfits:
            ship = calculator.build(game, hull, hull.stock_outfits)
            if not ship.fit_errors and ship.agility > 0:
                out[hull.name] = ship.agility
    return out


def resolve_percentiles(game: GameData, request: roles.Request) -> None:
    """Turn the request's minimums given as a share of stock ships ([must] min_percentile) into plain minimums."""
    if not request.must_percentile:
        return
    scales = reference_scales(game, request, list(request.must_percentile), minimum_ships=1, mode="all")
    for metric, share in request.must_percentile.items():
        values = scales[metric].values if metric in scales else []
        if values:
            value = values[min(len(values) - 1, int(share * len(values)))]
            request.must_min[metric] = max(request.must_min.get(metric, value), value)


def resolve_levers(game: GameData, request: roles.Request) -> None:
    """Turn request levers that need game data into numbers: [must] match (a band around a named hull's stock value),
    the war zone's incoming fire for the exposure window, and the target classes for jump denial."""
    role = request.role
    for metric, (name, within) in request.match.items():
        target = game.hulls.get(name) or game.variants.get(name)
        if target is None:
            raise roles.RoleError(f"[must] match: no hull named '{name}'")
        value = roles.metric_value(calculator.build(game, target, target.stock_outfits), role, metric)
        request.must_min[metric] = max(request.must_min.get(metric, -math.inf), value * (1 - within))
        request.must_max[metric] = min(request.must_max.get(metric, math.inf), value * (1 + within))
    if role.exposure_seconds and role.war_zone and not role.exposure_dps:
        role.exposure_dps = war_zone_dps(game, role.war_zone)
    uses = set(request.metrics) | set(request.must_min) | set(request.must_max)
    if uses & {"jump denial", "denial range"} and not role.denial_targets:
        role.denial_targets = denial_targets(game)


def _stock_ships(game: GameData, names) -> list[Ship]:
    hulls = {**game.hulls, **game.variants}
    out = []
    for name in dict.fromkeys(names):
        h = hulls.get(name)
        if h is None or h.deprecated or not h.stock_outfits:
            continue
        ship = calculator.build(game, h, h.stock_outfits)
        if not ship.fit_errors:
            out.append(ship)
    return out


def war_zone_dps(game: GameData, zone: str) -> float:
    """Incoming fire in a war zone (user): the strongest ship's damage per second plus 2 × the strongest among the
    fastest 20% of ships. The zone's battles go on forever, so any ship type can be there several times."""
    names = [s for g in calculator.WAR_ZONES[zone.lower()] for s in game.government_ships.get(g, [])]
    ships = _stock_ships(game, names)
    if not ships:
        return 0.0
    dps = lambda ship: 60 * sum(w.shield_damage + w.hull_damage for w in ship.weapons if w.offensive)
    fastest = sorted(ships, key=lambda ship: ship.max_speed, reverse=True)
    fast = fastest[:max(1, math.ceil(calculator.EXPOSURE_FAST_SHARE * len(ships)))]
    return max(map(dps, ships)) + calculator.EXPOSURE_FAST_COUNT * max(map(dps, fast))


def denial_targets(game: GameData) -> tuple:
    """Jump denial targets: the median stock light, medium and heavy warship (inertial mass, braking per frame,
    jump speed of its drive)."""
    out = []
    for category in ("Light Warship", "Medium Warship", "Heavy Warship"):
        ships = _stock_ships(game, [h.name for h in game.hulls.values() if h.category == category])
        rows = sorted((s.inertial_mass, s.get("thrust") * (1 + s.get("acceleration multiplier")) / s.inertial_mass,
                       s.get("jump speed") or 0.2) for s in ships if s.inertial_mass > 0)
        if rows:
            mid = rows[len(rows) // 2]
            out.append(mid)
    return tuple(out)


def reference_scales(game: GameData, request: roles.Request, metrics: list[str],
                     minimum_ships: int = REFERENCE_MIN_SHIPS, hull: Hull | None = None,
                     mode: str | None = None) -> dict[str, Scale]:
    """Each metric's distribution over the stock ships (models and variants as the game outfits them), chosen by
    `mode` (default: the request's; see REFERENCE_MODES). Narrow modes widen to the next mode where too few ships
    have the metric: class -> family -> all."""
    mode = mode or request.reference
    if mode == "stock":
        stock_ship = calculator.build(game, hull, hull.stock_outfits) if hull is not None and hull.stock_outfits else None
        fallback = reference_scales(game, request, metrics, minimum_ships, hull, "family")
        out: dict[str, Scale] = {}
        for m in metrics:
            v = roles.metric_value(stock_ship, request.role, m) if stock_ship is not None and not stock_ship.fit_errors else 0
            if v > 0:
                out[m] = StockScale(v)
            elif m in fallback:
                out[m] = fallback[m]
        return out
    samples: list[tuple[str, dict[str, float]]] = []
    for h in list(game.hulls.values()) + list(game.variants.values()):
        if h.deprecated or not h.has_sprite or not h.stock_outfits or source_group(h) == "scripted":
            continue
        if mode != "legacy" and h.category in EXCLUDED_CATEGORIES:
            continue
        ship = calculator.build(game, h, h.stock_outfits)
        if ship.fit_errors:
            continue
        samples.append((h.category, {m: roles.metric_value(ship, request.role, m) for m in metrics}))
    order = {"class": ["class", "family", "all"], "family": ["family", "all"]}.get(mode, [mode])
    out = {}
    for m in metrics:
        for step in order:
            if step == "class" and hull is not None:
                pool = [v[m] for c, v in samples if c == hull.category]
            elif step == "family" and hull is not None:
                family = _family(hull.category)
                pool = [v[m] for c, v in samples if c in family]
            else:
                pool = [v[m] for _, v in samples]
            pool = sorted(x for x in pool if x > 0)
            if len(pool) >= minimum_ships:
                out[m] = Scale(pool)
                break
    return out


BALANCE_EPS = 1e-9


def balance_spread(weights: dict[str, float], terms: dict[str, float]) -> tuple[float, float]:
    """Weighted mean and weighted standard deviation of the term scores (positively weighted terms only)."""
    total = sum(weights.values())
    if total <= 0:
        return 0.0, 0.0
    mean = sum(w * terms[n] for n, w in weights.items()) / total
    spread = math.sqrt(sum(w * (terms[n] - mean) ** 2 for n, w in weights.items()) / total)
    return mean, spread


def balance_weights(weights: dict[str, float], terms: dict[str, float], alpha: float) -> dict[str, float]:
    """Deviation weighting (user's spec, linear form): each positively weighted term's weight × max(0, 1 − α z),
    z = (score − weighted mean) / weighted spread, re-normalised so the total positive weight is unchanged. Terms
    below the route's mean get more weight, terms above get less; α = 0 or no spread leaves the weights as they are.
    Negatively weighted terms ([should_not]) keep their weight."""
    pos = {n: w for n, w in weights.items() if w > 0 and n in terms}
    mean, spread = balance_spread(pos, terms)
    out = dict(weights)
    if alpha <= 0 or spread <= BALANCE_EPS or not pos:
        return out
    scaled = {n: w * max(0.0, 1 - alpha * (terms[n] - mean) / (spread + BALANCE_EPS)) for n, w in pos.items()}
    total, new_total = sum(pos.values()), sum(scaled.values())
    for n, w in scaled.items():
        out[n] = w * total / new_total if new_total > 0 else pos[n]
    return out


class Scorer:
    """Exact score of a design: weighted metric scores, best over the request's routes."""

    def __init__(self, request: roles.Request, scales: dict[str, Scale]):
        self.request, self.scales = request, scales
        self.routes = request.routes or [roles.Route("", request.weights)]

    def term(self, name: str, metrics: dict[str, float]) -> float | None:
        """Score of one weighted term: a metric, or a product composite (weighted geometric mean of part scores)."""
        parts = self.request.products.get(name)
        if parts is None:
            return self.scales[name].score(self._capped(name, metrics)) if name in self.scales else None
        total = sum(parts.values())
        value = 1.0
        for m, w in parts.items():
            value *= max(0.0, self.scales[m].score(self._capped(m, metrics))) ** (w / total)
        return value

    def _capped(self, metric: str, metrics: dict[str, float]) -> float:
        """[should] up_to (S4): more counts up to the cap, nothing beyond it, and no penalty above it."""
        cap = self.request.up_to.get(metric)
        return metrics[metric] if cap is None else min(metrics[metric], cap)

    def term_slopes(self, name: str, metrics: dict[str, float]) -> dict[str, float]:
        """d(term score)/d(metric value) for each metric in the term, at these values."""
        parts = self.request.products.get(name)
        slope = lambda m: 0.0 if m in self.request.up_to and metrics[m] >= self.request.up_to[m] else \
            self.scales[m].slope(metrics[m])
        if parts is None:
            return {name: slope(name)} if name in self.scales else {}
        total = sum(parts.values())
        floored = {m: max(roles.PRODUCT_FLOOR, self.scales[m].score(self._capped(m, metrics))) for m in parts}
        value = math.prod(floored[m] ** (w / total) for m, w in parts.items())
        return {m: value * (w / total) / floored[m] * slope(m) for m, w in parts.items()}

    def combine(self, weights: dict[str, float], terms: dict[str, float]) -> float:
        """A route's score from its term scores: weighted sum, or a weighted power mean of the positively weighted
        terms (times their total weight) plus the negatively weighted ones as a sum. With a balance strength α > 0
        (deviation weighting, see `balance_spread`) the positively weighted part is W × (mean − α × spread)."""
        mode = self.request.combine
        if mode == "sum":
            alpha = self.request.balance
            if alpha > 0:
                pos = {n: w for n, w in weights.items() if w > 0 and n in terms}
                total = sum(pos.values())
                mean, spread = balance_spread(pos, terms)
                return total * (mean - alpha * spread) + sum(
                    w * terms[n] for n, w in weights.items() if w < 0 and n in terms)
            return sum(w * terms[n] for n, w in weights.items() if n in terms)
        p = float(mode.split(":")[1])
        pos = {n: w for n, w in weights.items() if w > 0 and n in terms}
        total = sum(pos.values()) or 1.0
        floored = {n: max(COMBINE_FLOOR, terms[n]) for n in pos}
        if p == 0:
            mean = math.exp(sum(w / total * math.log(floored[n]) for n, w in pos.items()))
        else:
            mean = sum(w / total * floored[n] ** p for n, w in pos.items()) ** (1 / p)
        return total * mean + sum(w * terms[n] for n, w in weights.items() if w < 0 and n in terms)

    def marginal_weights(self, weights: dict[str, float], metrics: dict[str, float]) -> dict[str, float]:
        """d(route score)/d(term score) at these metric values: the weights themselves for a plain sum; with a
        balance strength, weight × max(0, 1 − α z) (z: the term's standing against the route's other terms, in
        spreads), re-normalised to the same total, so lagging terms count more and leading ones less; for a power
        mean, weight × (mean / term score) ^ (1 − p), so the weakest terms count most."""
        if self.request.combine == "sum":
            if self.request.balance <= 0:
                return dict(weights)
            terms = {n: t for n in weights if (t := self.term(n, metrics)) is not None}
            return balance_weights(weights, terms, self.request.balance)
        terms = {n: t for n in weights if (t := self.term(n, metrics)) is not None}
        p = float(self.request.combine.split(":")[1])
        pos = {n: w for n, w in weights.items() if w > 0 and n in terms}
        total = sum(pos.values()) or 1.0
        mean = (self.combine(pos, terms)) / total
        out = {}
        for n, w in weights.items():
            if w > 0 and n in terms:
                out[n] = w * (mean / max(COMBINE_FLOOR, terms[n])) ** (1 - p)
            else:
                out[n] = w
        return out

    def route_scores(self, metrics: dict[str, float]) -> list[float]:
        out = []
        for r in self.routes:
            terms = {n: t for n in r.weights if (t := self.term(n, metrics)) is not None}
            out.append(self.combine(r.weights, terms))
        return out


@dataclass
class Design:
    outfits: dict[str, int]
    ship: Ship
    checks: list[Check]
    metrics: dict[str, float]
    score: float
    route_scores: list[float] = field(default_factory=list)
    route: str = ""
    start: str = ""                   # which starting design led here

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.passed is False]


@dataclass
class Result:
    hull: Hull
    status: str                       # "optimized" | "infeasible" | "no design passed the checks"
    design: Design | None = None
    closest: Design | None = None
    blockers: list[str] = field(default_factory=list)
    scales: dict[str, Scale] = field(default_factory=dict)
    starts: list[tuple[str, float | None]] = field(default_factory=list)   # (start, best exact score or None)
    polish_moves: int = 0
    jobs: int = 1
    threads: int = 1
    iterations: int = 0
    seconds: float = 0.0
    candidates: int = 0
    # Search diagnostics (visibility): solves that ran into their time limit, and the run's context (in-process only,
    # for tools that re-polish or probe the result).
    capped_solves: int = 0
    context: object = None


# --- Candidate outfits ---

def candidates(game: GameData, hull: Hull, settings: Settings, request: roles.Request) -> list[Outfit]:
    available = Availability(game, settings)
    boarding = bool(roles.BOARDING_METRICS & set(request.metrics + list(request.must_min) + request.must_have))
    blocked = tuple(c for c in NOT_INSTALLABLE if not (boarding and c == "Hand to Hand"))
    pool = []
    for o in game.outfits.values():
        if not o.category or o.category in blocked or o.attributes.get("installable", 0) < 0:
            continue
        if not available.outfit_ok(o) or not request.outfit_allowed(game, o) or not request.weapon_allowed(game, o):
            continue
        if not request.unique_outfits and (o.attributes.get("unique") or o.category == "Unique"):
            continue
        if request.role.goal == "capture-intact" and o.weapon is not None:
            w = calculator._weapon_stats(game, o, 1)
            if w.offensive and not w.instantaneous:
                continue
        pool.append(o)
    # Drop outfits that need a capacity nothing can supply (anchor points, spinal mounts, upgrade slots, ...).
    while True:
        supplied = {k for k, v in hull.attributes.items() if v > 0}
        supplied |= {k for o in pool for k, v in o.attributes.items() if v > 0}
        kept = [o for o in pool if all(
            v >= 0 or calculator.MINIMUMS.get(k, 0.0) is None or k in supplied or k == "required crew"
            for k, v in o.attributes.items())]
        if len(kept) == len(pool):
            return kept
        pool = kept


def _upper_bounds(hull: Hull, pool: list[Outfit]) -> dict[str, int]:
    providers: dict[str, float] = {}
    for o in pool:
        for k, v in o.attributes.items():
            if v > 0:
                providers[k] = providers.get(k, 0.0) + v * 10
    bounds = {}
    for o in pool:
        ub = 1 if o.attributes.get("unique") else 400
        for k, v in o.attributes.items():
            minimum = calculator.MINIMUMS.get(k, 0.0)
            if v >= 0 or minimum is None or k == "required crew":
                continue
            room = hull.attributes.get(k, 0.0) - minimum + providers.get(k, 0.0)
            ub = min(ub, max(0, math.floor(room / -v + 1e-9)))
        bounds[o.name] = ub
    return bounds


# --- Evaluation with the calculator ---

def evaluate_design(game: GameData, hull: Hull, outfits: dict[str, int], request: roles.Request,
                    scorer: Scorer, disruption: bool, targets: list[Ship] | None,
                    ship: Ship | None = None) -> Design:
    ship = ship or calculator.build(game, hull, outfits)
    checks = roles.check_request(ship, request, game) + calculator.evaluate(ship, request.role, disruption, targets)
    metrics = {m: roles.metric_value(ship, request.role, m) for m in request.metrics}
    scores = scorer.route_scores(metrics)
    if not roles.asks_for_reverse(request):
        level = roles.reverse_level(ship)
        bonus = -REVERSE_USELESS_PENALTY if level == "useless" else REVERSE_BONUS if level != "none" else 0.0
        scores = [s + bonus for s in scores]
    best = max(range(len(scores)), key=scores.__getitem__)
    return Design({k: v for k, v in outfits.items() if v}, ship, checks, metrics, scores[best], scores,
                  scorer.routes[best].label)


def waste(outfit: Outfit) -> float:
    """Outfit space and cargo space an outfit uses up, plus one for fitting it (the tie-break between otherwise
    equal designs)."""
    a = outfit.attributes
    return 1.0 - min(0.0, a.get("outfit space", 0.0)) - min(0.0, a.get("cargo space", 0.0))


def design_waste(game: GameData, outfits: dict[str, int]) -> float:
    return sum(waste(game.outfits[n]) * c for n, c in outfits.items())


def balance(game: GameData, ship: Ship) -> dict[str, float]:
    """How the design spends its capacities: shares of weapon and engine capacity used, and outfit space split
    between engines, weapons, everything else and free space."""
    def used(key: str) -> tuple[float, float]:
        spent = sum(-min(0.0, game.outfits[n].attributes.get(key, 0.0)) * c for n, c in ship.outfits.items())
        total = ship.hull.attributes.get(key, 0.0) + sum(
            max(0.0, game.outfits[n].attributes.get(key, 0.0)) * c for n, c in ship.outfits.items())
        return spent, total
    w_used, w_total = used("weapon capacity")
    e_used, e_total = used("engine capacity")
    _, space = used("outfit space")
    split = {"engines": 0.0, "weapons": 0.0, "other": 0.0}
    # Outfits that supply something only the installed weapons use (an Optical Lasing Generator's lasing power)
    # count as weapons.
    shared = {"outfit space", "weapon capacity", "engine capacity", "gun ports", "turret mounts", "required crew",
              "cargo space", "bunks"}
    weapon_needs = {k for n in ship.outfits if game.outfits[n].weapon is not None
                    for k, v in game.outfits[n].attributes.items() if v < 0 and k not in shared}
    for n, c in ship.outfits.items():
        a = game.outfits[n].attributes
        supports = any(a.get(k, 0) > 0 for k in weapon_needs)
        kind = ("engines" if a.get("engine capacity", 0) < 0 else
                "weapons" if a.get("weapon capacity", 0) < 0 or game.outfits[n].weapon is not None or supports
                else "other")
        split[kind] += -min(0.0, a.get("outfit space", 0.0)) * c
    out = {"weapon capacity used": w_used / w_total if w_total else 0.0,
           "engine capacity used": e_used / e_total if e_total else 0.0}
    for kind, v in split.items():
        out[f"outfit space: {kind}"] = v / space if space else 0.0
    out["outfit space: free"] = ship.get("outfit space") / space if space else 0.0
    return out


# --- The linear model ---

class _Model:
    """CP-SAT model of the request, linearized around a design `point`."""

    def __init__(self, game: GameData, hull: Hull, pool: list[Outfit], bounds: dict[str, int],
                 request: roles.Request, point: Ship, cuts: list[dict[str, int]],
                 budgets: tuple[float, float] | None = None, band: float | None = None):
        self.game, self.hull, self.pool, self.request, self.point = game, hull, pool, request, point
        self.role: Role = request.role
        self.m = cp_model.CpModel()
        self.bounds = bounds
        self.x = {o.name: self.m.NewIntVar(0, bounds[o.name], o.name) for o in pool}
        self.zero = self.m.NewIntVar(0, 0, "zero")       # keeps every expression a CP-SAT expression
        self.groups: dict[str, cp_model.IntVar] = {}
        self.weapon_unit = {o.name: calculator._weapon_stats(game, o, 1) for o in pool if o.weapon is not None}
        self._slopes: dict[str, tuple[dict[str, float], float]] = {}
        self._build()
        for cut in cuts:
            self._exclude(cut)
        if budgets is not None:
            # Weapon and engine budgets: at most this share of the hull's capacity goes to those outfits.
            for key, share in zip(("weapon capacity", "engine capacity"), budgets):
                total = hull.attributes.get(key, 0.0)
                if total > 0 and share < 1:
                    self.m.Add(self.attr(key) >= round((1 - share) * total * SCALE))
        if band is not None:
            mass = point.mass
            self.m.Add(self.mass() <= round(mass * (1 + band) * SCALE))
            self.m.Add(self.mass() >= round(mass * (1 - band) * SCALE))

    # helpers
    def group(self, name: str) -> cp_model.IntVar:
        if name not in self.groups:
            self.groups[name] = self.m.NewBoolVar(name)
        return self.groups[name]

    def attr(self, key: str, scale: float = 1.0):
        """Scaled linear expression for an attribute total."""
        terms = [round(o.attributes[key] * scale * SCALE) * self.x[o.name] for o in self.pool if o.attributes.get(key)]
        return sum(terms) + round(self.hull.attributes.get(key, 0.0) * scale * SCALE) + self.zero

    def per_outfit(self, values: dict[str, float], const: float = 0.0):
        return sum(round(v * SCALE) * self.x[n] for n, v in values.items() if v) + round(const * SCALE) + self.zero

    def mass(self):
        return self.per_outfit({o.name: o.mass for o in self.pool}, self.hull.mass)

    def require(self, group: str, constraint) -> None:
        self.m.Add(constraint).OnlyEnforceIf(self.group(group))

    def _exclude(self, outfits: dict[str, int]) -> None:
        differs = []
        for name, var in self.x.items():
            value = outfits.get(name, 0)
            b = self.m.NewBoolVar("")
            self.m.Add(var != value).OnlyEnforceIf(b)
            self.m.Add(var == value).OnlyEnforceIf(b.Not())
            differs.append(b)
        self.m.AddBoolOr(differs)

    def linear_metric(self, metric: str) -> tuple[dict[str, float], float]:
        """Per-outfit change in a metric around the current point, and its value there."""
        if metric not in self._slopes:
            self._slopes[metric] = self._linear_metric(metric)
        return self._slopes[metric]

    def _linear_metric(self, metric: str) -> tuple[dict[str, float], float]:
        point, role, game = self.point, self.role, self.game
        base = roles.metric_value(point, role, metric)
        if metric not in roles.METRICS:
            values = {o.name: o.attributes.get(metric, 0.0) for o in self.pool}
            return values, base - sum(values[n] * c for n, c in point.outfits.items() if n in values)
        slopes = {}
        for o in self.pool:
            trial = dict(point.outfits)
            trial[o.name] = trial.get(o.name, 0) + 1
            slopes[o.name] = roles.metric_value(calculator.build(game, self.hull, trial), role, metric) - base
        return slopes, base - sum(slopes[n] * c for n, c in point.outfits.items() if n in slopes)

    # constraints
    def _build(self) -> None:
        m, role, point, hull = self.m, self.role, self.point, self.hull
        category = hull.category
        carried = category in calculator.CARRIED_CATEGORIES
        interceptor = category == "Interceptor"
        fighter_rules = role.fighter or carried

        # Fit rule.
        touched = {k for o in self.pool for k, v in o.attributes.items() if v < 0}
        automaton = hull.attributes.get("automaton", 0) > 0
        for key in touched:
            minimum = calculator.MINIMUMS.get(key, 0.0)
            if key == "required crew":
                minimum = 0.0 if automaton else 1.0
            if minimum is not None:
                self.require("fit", self.attr(key) >= round(minimum * SCALE))

        self.require("can move", self.attr("thrust") >= 1)
        self.require("can move", self.attr("turn") >= 1)
        if role.needs_drives and not carried:
            excluded = role.excluded_drives | ({"jump drive"} if interceptor else set())
            for drive in ("hyperdrive", "jump drive", "quantum keystone"):
                if drive not in excluded:
                    self.require("drives", self.attr(drive) >= 1)
        if role.needs_ramscoop and not (carried or interceptor):
            self.require("ramscoop", self.attr("ramscoop") >= 1)
        am = [self.x[n] for n, w in self.weapon_unit.items() if w.anti_missile]
        if role.needs_anti_missile and not (fighter_rules or interceptor):
            self.require("anti-missile", sum(am) + self.zero >= 1)
        if role.hero:
            self.require("no afterburner (hero)", self.attr("afterburner thrust") <= 0)
        for name in self.request.must_outfits:
            if name in self.x:
                self.require("must have outfit", self.x[name] >= 1)
            else:
                self.require("must have outfit: not available", self.zero >= 1)
        if role.needs_regen:
            regen = (self.attr("shield generation") + self.attr("delayed shield generation")
                     + self.attr("hull repair rate") + self.attr("delayed hull repair rate"))
            self.require("regeneration", regen >= 1)

        # Energy and heat scenarios, at the 90% heat target, with the cooling efficiency, heat dissipation and
        # regeneration multipliers of the current point.
        d = point.get("heat dissipation")
        bounds_of = lambda o: self.bounds[o.name]
        solar_on = 0.0 if role.must_run_dark else 1.0
        w_energy = {n: w.energy for n, w in self.weapon_unit.items()}
        w_heat = {n: w.heat for n, w in self.weapon_unit.items()}
        regen_e = {o.name: self._regen(o, "energy") for o in self.pool}
        regen_h = {o.name: self._regen(o, "heat") for o in self.pool}
        idle_energy = self.attr("energy generation") + self.attr("fuel energy") - self.attr("energy consumption")
        idle_heat = self.attr("heat generation") + self.attr("fuel heat")
        cooling_draw = self.attr("cooling energy", 0.9)
        # Removal capacity at 90% heat: 0.9 × (0.1 × d × (mass + heat capacity) + e × active cooling) + e × cooling.
        # Cooling efficiency e depends on total cooling inefficiency through an S-curve, so each possible level
        # (rounded up, which is conservative) gets its own exact linear constraint.
        passive = (sum(round(0.09 * d * o.mass * SCALE) * self.x[o.name] for o in self.pool)
                   + round(0.09 * d * hull.mass * SCALE) + self.attr("heat capacity", 0.09 * d))
        max_level = math.ceil(sum(max(0.0, o.attributes.get("cooling inefficiency", 0.0)) * bounds_of(o)
                                  for o in self.pool) + max(0.0, hull.attributes.get("cooling inefficiency", 0.0)))
        max_level = min(max_level, 30)
        level = m.NewIntVar(0, max_level, "cooling inefficiency level")
        inefficiency = self.attr("cooling inefficiency")
        m.Add(level * SCALE >= inefficiency)
        m.Add(level * SCALE < inefficiency + SCALE)
        self.removal_by_level = []
        for k in range(max_level + 1):
            e_k = 1.0 if k == 0 else 2 + 2 / (1 + math.exp(-k / 2)) - 4 / (1 + math.exp(-k / 4))
            is_k = m.NewBoolVar(f"level {k}")
            m.Add(level == k).OnlyEnforceIf(is_k)
            m.Add(level != k).OnlyEnforceIf(is_k.Not())
            removal_k = passive + self.attr("active cooling", 0.9 * e_k) + self.attr("cooling", e_k)
            self.removal_by_level.append((is_k, removal_k))

        def heat_ok(group: str, heat_in) -> None:
            for is_k, removal_k in self.removal_by_level:
                m.Add(heat_in <= removal_k).OnlyEnforceIf([self.group(group), is_k])

        def load(share: float):
            """Energy and heat use with weapons at `share`, plus the worst movement or regeneration load."""
            moves = {"regen": (self.per_outfit(regen_e), self.per_outfit(regen_h)),
                     "thrust": (self.attr("thrusting energy"), self.attr("thrusting heat")),
                     "turn": (self.attr("turning energy"), self.attr("turning heat"))}
            worst_e = m.NewIntVar(-10**15, 10**15, "")
            worst_h = m.NewIntVar(-10**15, 10**15, "")
            if point.has_torch:
                rest_e = m.NewIntVar(-10**15, 10**15, "")
                rest_h = m.NewIntVar(-10**15, 10**15, "")
                for k in ("regen", "turn"):
                    m.Add(rest_e >= moves[k][0])
                    m.Add(rest_h >= moves[k][1])
                for t in calculator.thrust_shares(point):       # agility of the current point
                    m.Add(worst_e * 1000 >= round(t * 1000) * moves["thrust"][0] + round((1 - t) * 1000) * rest_e)
                    m.Add(worst_h * 1000 >= round(t * 1000) * moves["thrust"][1] + round((1 - t) * 1000) * rest_h)
            else:
                for energy, heat in moves.values():
                    m.Add(worst_e >= energy)
                    m.Add(worst_h >= heat)
            weapons_e = self.per_outfit({n: v * share for n, v in w_energy.items()})
            weapons_h = self.per_outfit({n: v * share for n, v in w_heat.items()})
            return weapons_e + worst_e, weapons_h + worst_h

        def heat_within(group: str, parts: list[tuple[float, object]]) -> None:
            """Σ coefficient × heat input ≤ removal (coefficients from the heat curve: see _timed)."""
            expr = sum(round(c * 1000) * e for c, e in parts if round(c * 1000)) + self.zero
            for is_k, removal_k in self.removal_by_level:
                m.Add(expr <= removal_k * 1000).OnlyEnforceIf([self.group(group), is_k])

        # Every ship, out of combat: cruising indefinitely (thrust 70%, turn 30%, idle draw).
        f = calculator.solar_factor(role)
        made = point.get("thrusting energy") < 0
        thrust_share = calculator.CRUISE_THRUST * (min(1.0, point.agility / calculator.GUN_FULL_AGILITY) if made else 1.0)
        cruise_e = self.attr("thrusting energy", thrust_share) + self.attr("turning energy", calculator.CRUISE_TURN)
        cruise_h = (self.attr("thrusting heat", calculator.CRUISE_THRUST)
                    + self.attr("turning heat", calculator.CRUISE_TURN))
        if role.cloak_duty:
            cruise_e = cruise_e + self.attr("cloaking energy", role.cloak_duty)
            cruise_h = cruise_h + self.attr("cloaking heat", role.cloak_duty)
        base_net = idle_energy + self.attr("solar collection", f * solar_on) - cruise_e
        cruise_in = idle_heat + cruise_h + self.attr("solar heat", f)
        heat_ok("cruising heat", cruise_in)
        self.require("cruising energy", base_net - cooling_draw >= 0)
        cooling_full = self.attr("cooling energy")
        capacity = self.attr("energy capacity")
        kp = 0.001 * d + (point.cooling_efficiency * point.get("active cooling") / point.max_heat
                          if point.max_heat else 0.0)
        q = lambda frames: (1 - min(kp, 1.0)) ** frames

        def timed(group: str, phases: list[tuple[float, object, object]], start_in=None) -> None:
            """Phases of (frames, net energy, heat input) from full batteries and cruising heat (or the equilibrium
            of `start_in`): stored energy stays ≥ 0 at every phase end, and heat ≤ 90% (heat after a phase =
            (1 − q) × its equilibrium + q × the heat before, so each phase end is a weighted sum of heat inputs)."""
            energy = capacity
            weights: list[tuple[float, object]] = [(1.0, cruise_in if start_in is None else start_in)]
            for frames, net, heat_in in phases:
                if frames <= 0:
                    continue
                energy = energy + net * round(frames)
                self.require(group, energy >= 0)
                qf = q(frames)
                weights = [(c * qf, e) for c, e in weights] + [(1 - qf, heat_in)]
                heat_within(group, weights)

        shield_e = self.per_outfit({o.name: self._regen_part(o, "shield", "energy") for o in self.pool})
        shield_h = self.per_outfit({o.name: self._regen_part(o, "shield", "heat") for o in self.pool})
        hull_e = self.per_outfit({o.name: self._regen_part(o, "hull", "energy") for o in self.pool})
        hull_h = self.per_outfit({o.name: self._regen_part(o, "hull", "heat") for o in self.pool})
        t_shields, t_hull = calculator.regen_times(point)       # durations at the current point
        if t_shields or t_hull:
            for long_shields in (True, False):
                ts = (t_shields or 0.0) * (calculator.RECOVERY_LONG if long_shields else 1.0)
                th = (t_hull or 0.0) * (1.0 if long_shields else calculator.RECOVERY_LONG)
                rest_e, rest_h = (shield_e, shield_h) if ts > th else (hull_e, hull_h)
                timed("recovery", [(min(ts, th), base_net - cooling_full - shield_e - hull_e,
                                    cruise_in + shield_h + hull_h),
                                   (abs(ts - th), base_net - cooling_full - rest_e, cruise_in + rest_h)])

        share = 1.0 if role.combat and not fighter_rules else calculator.WEAPON_SHARE_NON_COMBAT
        if role.combat and not fighter_rules and not interceptor:
            # The designed fight(s) on batteries: all primaries, secondaries in their window, regen draw, and
            # recovery gaps between chained fights.
            primary = {n: w for n, w in self.weapon_unit.items() if not w.secondary}
            secondary = {n: w for n, w in self.weapon_unit.items() if w.secondary}
            primary_e = self.per_outfit({n: calculator.PRIMARY_SHARE * w.energy for n, w in primary.items()})
            primary_h = self.per_outfit({n: calculator.PRIMARY_SHARE * w.heat for n, w in primary.items()})
            sec_e = self.per_outfit({n: calculator.SECONDARY_SHARE * w.energy for n, w in secondary.items()})
            sec_h = self.per_outfit({n: calculator.SECONDARY_SHARE * w.heat for n, w in secondary.items()})
            longest = max((f for f, _ in role.fight_chain), default=role.fight_seconds) * calculator.FPS
            suffice = t_shields is not None and t_shields <= calculator.SHIELD_SELF_SUFFICIENT * longest
            regen_e = shield_e + (0 if suffice else hull_e)
            regen_h = shield_h + (0 if suffice else hull_h)
            net = base_net - cooling_full - primary_e - regen_e
            heat_in = cruise_in + primary_h + regen_h
            phases = []
            for frames, firing, secondaries in calculator.combat_plan(role):
                if firing:
                    phases.append((frames, net - sec_e if secondaries else net,
                                   heat_in + sec_h if secondaries else heat_in))
                else:
                    phases.append((frames, base_net - cooling_full - shield_e - hull_e,
                                   cruise_in + shield_h + hull_h))
            hot = None
            if role.start_state == "hot":
                hot = idle_heat + self.attr("thrusting heat") + self.attr("solar heat", calculator.stay_factor(role))
            timed("combat", phases, hot)
        elif interceptor:
            load_e, load_h = load(calculator.WEAPON_SHARE_NON_COMBAT)
            f = calculator.solar_factor(role)
            frames = calculator.INTERCEPTOR_BATTLE_FRAMES
            drain = load_e + cooling_draw - idle_energy - self.attr("solar collection", f * solar_on)
            self.require("interceptor reserves", drain * frames <= self.attr("energy capacity"))
            heat_ok("interceptor reserves", idle_heat + load_h + self.attr("solar heat", f))   # conservative
        else:
            load_e, load_h = load(share)
            f = calculator.solar_factor(role)
            heat_ok("combat heat", idle_heat + load_h + self.attr("solar heat", f))
            self.require("combat energy",
                         idle_energy + self.attr("solar collection", f * solar_on) - load_e - cooling_draw >= 0)
        f = calculator.stay_factor(role)
        thrust_e, thrust_h = self.attr("thrusting energy"), self.attr("thrusting heat")
        heat_ok("bright-star heat", idle_heat + thrust_h + self.attr("solar heat", f))
        self.require("bright-star energy",
                     idle_energy + self.attr("solar collection", f * solar_on) - thrust_e - cooling_draw >= 0)
        if role.evader:
            f = calculator.SOLAR_EVADING
            heat_ok("evading heat", idle_heat + self.attr("cloaking heat") + self.attr("solar heat", f))
            self.require("evading energy", idle_energy + self.attr("solar collection", f * solar_on)
                         - self.attr("cloaking energy") - cooling_draw >= 0)
        if not (role.combat and not fighter_rules) and not interceptor:
            extra = self.per_outfit({n: v * (1 - share) * calculator.BURST_FRAMES for n, v in w_energy.items()})
            self.require("burst energy", extra <= self.attr("energy capacity"))

        # Energy per shot (Ship::FlightCheck): a fitted weapon needs one shot's energy within the energy capacity
        # plus one frame of net generation.
        surge = (self.attr("energy capacity") + idle_energy
                 + self.attr("solar collection", calculator.solar_factor(role) * solar_on))
        for n, w in self.weapon_unit.items():
            if w.shot_energy > 0:
                fitted = m.NewBoolVar("")
                m.Add(self.x[n] == 0).OnlyEnforceIf(fitted.Not())
                m.Add(surge >= round(w.shot_energy * SCALE)).OnlyEnforceIf([fitted, self.group("energy per shot")])

        # Magazine depth.
        needs: dict[str, dict[str, float]] = {}
        for n, w in self.weapon_unit.items():
            if w.ammo and not w.ammo_rate:       # "ammo X 0": needs X installed, doesn't use it up
                if w.ammo in self.x:
                    self.require("magazine", self.x[n] <= self.bounds[n] * self.x[w.ammo])
                else:
                    self.require("magazine", self.x[n] == 0)
            elif w.ammo:
                frames = role.fight_seconds * calculator.FPS * calculator.magazine_window(w, role.fight_seconds)
                needs.setdefault(w.ammo, {})[n] = w.ammo_rate * frames * role.fights_per_restock
        for ammo, per_weapon in needs.items():
            if ammo in self.x:
                self.require("magazine", self.x[ammo] * SCALE >= self.per_outfit(per_weapon))
            else:
                for n in per_weapon:
                    self.require("magazine", self.x[n] == 0)

        # Fuel for a fight (ramscoop recovery ignored here: conservative) and long-range refuelling.
        jump = point.average_jump_fuel or 100.0
        if role.combat:
            burn = self.attr("thrusting fuel", calculator.CRUISE_THRUST * role.fight_seconds * calculator.FPS)
            if not role.hero:
                burn = burn + self.attr("afterburner fuel", 0.10 * role.fight_seconds * calculator.FPS)
            self.require("fuel for a fight", self.attr("fuel capacity") >= burn + round(jump * SCALE))
        if role.long_range:
            wind = calculator.BEST_WIND[min(max(point.jumps, 1), 9)]
            need = (jump / (0.03 * wind * calculator.REFUEL_SCALE * calculator.FAST_FORWARD_REFUEL_FRAMES)) ** 2
            self.require("refuel (long range)", self.attr("ramscoop") >= round(need * SCALE))

        # The role's hard requirements.
        req = self.request
        for metric, minimum in req.must_min.items():
            values, const = self.linear_metric(metric)
            self.require(f"must: {metric} ≥ {minimum:g}", self.per_outfit(values, const) >= round(minimum * SCALE))
        for metric, maximum in req.must_max.items():
            values, const = self.linear_metric(metric)
            self.require(f"must: {metric} ≤ {maximum:g}", self.per_outfit(values, const) <= round(maximum * SCALE))
        for metric in req.must_have:
            values, const = self.linear_metric(metric)
            self.require(f"must have: {metric}", self.per_outfit(values, const) >= 1)
        for metric in req.must_not:
            for o in self.pool:
                if metric in roles.METRICS:
                    values, _ = self.linear_metric(metric)
                    if values.get(o.name, 0) > 0:
                        self.require(f"must not have: {metric}", self.x[o.name] == 0)
                    continue
                if o.attributes.get(metric, 0) > 0:
                    self.require(f"must not have: {metric}", self.x[o.name] == 0)
        if req.reverse_thrust:
            u, t = self.attr("turn"), self.attr("thrust")
            r = self.attr("reverse thrust")
            if req.reverse_thrust == "balanced":
                self.require("must: reverse thrust", r * 60 >= u)
            elif req.reverse_thrust == "nimble":
                self.require("must: reverse thrust", r * 120 >= u + 60 * t)
            else:
                pt, pu, pd = point.get("thrust"), point.get("turn"), point.get("drag")
                ratio = pu / (pu + 180 * pd) if pu + 180 * pd > 0 else 0.0
                self.require("must: reverse thrust", r * 1000 >= round(ratio * 1000) * t)
                self.require("must: reverse thrust", r >= 1)

    def _regen_part(self, o: Outfit, kind: str, resource: str) -> float:
        """Per-frame energy or heat of one outfit's shield or hull regeneration, at the point's multipliers."""
        base = o.attributes.get(f"{kind} {resource}", 0.0) + o.attributes.get(f"delayed {kind} {resource}", 0.0)
        return base * (1 + self.point.get(f"{kind} {resource} multiplier"))

    def _regen(self, o: Outfit, resource: str) -> float:
        p = self.point
        value = 0.0
        for kind in ("shield", "hull"):
            base = o.attributes.get(f"{kind} {resource}", 0.0) + o.attributes.get(f"delayed {kind} {resource}", 0.0)
            value += base * (1 + p.get(f"{kind} {resource} multiplier"))
        return value

    # solving
    def set_objective(self, weights: dict[str, float], scorer: "Scorer") -> None:
        """Maximize the weighted term scores, linearized at the current point."""
        total = {}
        names = {m for t in weights for m in self.request.products.get(t, [t])}
        at = {m: roles.metric_value(self.point, self.role, m) for m in names}
        weights = scorer.marginal_weights(weights, at)
        for term, weight in weights.items():
            if not weight:
                continue
            for metric, slope in scorer.term_slopes(term, at).items():
                values, _ = self.linear_metric(metric)
                for name, v in values.items():
                    total[name] = total.get(name, 0.0) + weight * slope * v
        for o in self.pool:
            total[o.name] = total.get(o.name, 0.0) - WASTE_PENALTY * waste(o)
        self.m.Maximize(sum(round(v * OBJECTIVE_SCALE) * self.x[n] for n, v in total.items()
                            if round(v * OBJECTIVE_SCALE)) + self.zero)

    def solve(self, seconds: float, enabled: set[str] | None = None,
              hint: dict[str, int] | None = None) -> dict[str, int] | None:
        if hint is not None:
            self.m.ClearHints()
            for name, var in self.x.items():
                self.m.AddHint(var, hint.get(name, 0))
        assumptions = [lit for name, lit in self.groups.items() if enabled is None or name in enabled]
        off = [lit for name, lit in self.groups.items() if enabled is not None and name not in enabled]
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = seconds
        solver.parameters.num_workers = _threads
        solver.parameters.relative_gap_limit = 0.002     # the objective is a linearization anyway
        self.m.ClearAssumptions()
        self.m.AddAssumptions(assumptions + [lit.Not() for lit in off])
        status = solver.Solve(self.m)
        self.capped = status == cp_model.FEASIBLE       # stopped at the time limit, not proven within the gap
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return {n: solver.Value(v) for n, v in self.x.items() if solver.Value(v)}


# --- Driver ---

def _grid(budget: tuple[float, float], capacity: float) -> list[float]:
    low, high = budget
    if capacity <= 0 or high - low < 0.01:
        return [high]
    n = 2 if high - low <= 0.2 else BUDGET_STEPS
    return [round(high - (high - low) * i / (n - 1), 3) for i in range(n)]


def _ideals(game, hull, pool, bounds, request, metrics, first, seconds) -> dict[str, Scale]:
    """Fallback scales: the best this hull reaches for each metric alone."""
    scales = {}
    for metric in metrics:
        point = calculator.build(game, hull, first)
        best = 0.0
        for _ in range(2):
            model = _Model(game, hull, pool, bounds, request, point, [])
            model.set_objective({metric: 1.0}, Scorer(request, {metric: Scale(ideal=1.0)}))
            found = model.solve(seconds, hint=point.outfits) or first
            point = calculator.build(game, hull, found)
            best = max(best, roles.metric_value(point, request.role, metric))
        scales[metric] = Scale(ideal=best if best > 0 else 1.0)
    return scales


@dataclass
class _Context:
    """Everything a start or a polish needs; sent once to each worker process."""
    game: GameData
    hull: Hull
    pool: list[Outfit]
    bounds: dict[str, int]
    request: roles.Request
    scales: dict[str, Scale]
    disruption: bool
    capture_targets: list[Ship] | None
    seed: Ship
    seconds_per_solve: float
    iterations_per_start: int
    max_cuts: int
    threads: int

    def scorer(self) -> Scorer:
        return Scorer(self.request, self.scales)

    def judge(self):
        scorer = self.scorer()
        return lambda outfits, ship=None: evaluate_design(self.game, self.hull, outfits, self.request, scorer,
                                                          self.disruption, self.capture_targets, ship)


@dataclass
class _StartResult:
    label: str
    best: Design | None
    closest: Design | None
    iterations: int
    lines: list[str]
    capped: int = 0


def _run_start(ctx: _Context, route_index: int, w_share: float, e_share: float, log=None) -> _StartResult:
    """One starting design: linearize, solve, check, in a shrinking mass band, for one route and budget."""
    scorer, judge = ctx.scorer(), ctx.judge()
    game, hull, pool, bounds, request = ctx.game, ctx.hull, ctx.pool, ctx.bounds, ctx.request
    route = scorer.routes[route_index]
    label = ", ".join(x for x in (route.label, f"weapons ≤ {w_share:.0%}", f"engines ≤ {e_share:.0%}") if x)
    lines: list[str] = []

    def note(text: str) -> None:
        lines.append(text)
        if log:
            log(text)

    cuts: list[dict[str, int]] = []
    failed_once: set[tuple] = set()
    closest: Design | None = None
    point, band, best_here, failures, steps, iterations = ctx.seed, None, None, 0, 0, 0
    capped = 0
    for _ in range(ctx.iterations_per_start + ctx.max_cuts):
        if failures > ctx.max_cuts or band is not None and band < MIN_MASS_BAND:
            break
        iterations += 1
        model = _Model(game, hull, pool, bounds, request, point, cuts, (w_share, e_share), band)
        model.set_objective(route.weights, scorer)
        found = model.solve(ctx.seconds_per_solve * (3 if band is None else 1), hint=point.outfits)
        capped += getattr(model, "capped", False)
        if found is None:
            note(f"{label}: no solution (band {band})")
            if band is None:
                break
            band /= 2
            continue
        design = judge(found)
        note(f"{label}: band {band}, score {design.score:.3f} "
             f"{'route ' + format(design.route_scores[route_index], '.3f') if not design.failed else ''}"
             f"{'FAILS ' + ', '.join(c.name for c in design.failed) if design.failed else ''}")
        if design.failed:
            if closest is None or len(design.failed) < len(closest.failed):
                closest = design
            # Usually the linearization was off (heat dissipation or regen multipliers changed with the step):
            # linearize again at the failing design. Exclude it only if the model returns it again.
            key = tuple(sorted(found.items()))
            if key in failed_once:
                cuts.append(found)
            else:
                failed_once.add(key)
                point = design.ship
            failures += 1
            continue
        own = design.route_scores[route_index]
        if best_here is None or own > best_here.route_scores[route_index] + 1e-9:
            best_here, point = design, design.ship
            band = MASS_BAND if band is None else min(1.0, band * 1.5)
        else:
            band = (band or MASS_BAND) / 2
        steps += 1
        if steps >= ctx.iterations_per_start:
            break
    if best_here is not None:
        best_here.start = label
    return _StartResult(label, best_here, closest, iterations, lines, capped)


def _run_polish(ctx: _Context, design: Design, seconds: float) -> tuple[Design, int]:
    polished, moves = polish(ctx.game, ctx.hull, ctx.pool, ctx.bounds, design, ctx.judge(),
                             time.monotonic() + seconds)
    polished.start = design.start
    return polished, moves


# Worker processes get the context once, at start-up.
_worker_ctx: _Context | None = None


def _worker_init(ctx: _Context) -> None:
    global _worker_ctx, _threads
    from . import tuning
    tuning.load_from_environment()       # calibration overrides made in the parent process
    _worker_ctx, _threads = ctx, ctx.threads


def _worker_start(args) -> _StartResult:
    return _run_start(_worker_ctx, *args)


def _worker_polish(args) -> tuple[Design, int]:
    return _run_polish(_worker_ctx, *args)


def optimize(game: GameData, hull: Hull, request: roles.Request, settings: Settings,
             seconds_per_solve: float = 2.0, iterations_per_start: int = 4, max_cuts: int = 20,
             polish_seconds: float = 60.0, capture_targets: list[Ship] | None = None, log=None,
             jobs: int | None = None, threads: int | None = None) -> Result:
    """`jobs` worker processes run the starting designs and the polish side by side (1: all in this process);
    `threads` is CP-SAT threads per solve. Both default from the CPUs available (see plan_parallelism)."""
    global _threads
    start = time.monotonic()
    log = log or (lambda text: None)
    if not request.role.reference_weapons:
        request.role.reference_weapons = reference_weapons(game, settings)
        request.role.stock_agility = stock_agility(game)
    resolve_percentiles(game, request)
    resolve_levers(game, request)
    pool = candidates(game, hull, settings, request)
    bounds = _upper_bounds(hull, pool)
    available = Availability(game, settings)
    for o in pool:
        limit = available.copy_limit(o)
        if limit is not None:
            bounds[o.name] = min(bounds[o.name], limit)
    disruption = any(o.weapon is not None and o.weapon.stats.get("disruption damage", 0) > 0 for o in pool)
    if request.role.goal == "capture-intact" and capture_targets is None:
        capture_targets = [calculator.build(game, t, t.stock_outfits) for t in calculator.default_capture_targets(game)]
    result = Result(hull, "infeasible", candidates=len(pool))
    empty = calculator.build(game, hull, {})

    # The sequential solves before the starts use every CPU.
    _threads = min(MAX_SOLVER_THREADS, available_cpus())
    # Is there any design at all? If not, find what blocks it.
    model = _Model(game, hull, pool, bounds, request, empty, [])
    first = model.solve(seconds_per_solve * 3)
    if first is None:
        result.blockers = _blockers(model, seconds_per_solve * 3)
        result.seconds = time.monotonic() - start
        return result

    metrics = request.metrics
    scales = reference_scales(game, request, metrics, hull=hull)
    missing = [m for m in metrics if m not in scales]
    scales.update(_ideals(game, hull, pool, bounds, request, missing, first, seconds_per_solve))
    result.scales = scales
    scorer = Scorer(request, scales)

    # The starting point to linearize at: the hull's stock design if it fits, else the feasible design.
    stock = calculator.build(game, hull, hull.stock_outfits) if hull.stock_outfits else None
    seed = stock if stock is not None and not stock.fit_errors and stock.outfits else calculator.build(game, hull, first)

    starts = [(r, w, e) for r in range(len(scorer.routes))
              for w in _grid(request.weapons_budget, hull.attributes.get("weapon capacity", 0.0))
              for e in _grid(request.engines_budget, hull.attributes.get("engine capacity", 0.0))]
    jobs, threads = plan_parallelism(len(starts), jobs, threads)
    result.jobs, result.threads = jobs, threads
    log(f"{len(starts)} starting designs, {jobs} at a time, {threads} solver threads each")
    ctx = _Context(game, hull, pool, bounds, request, scales, disruption, capture_targets, seed,
                   seconds_per_solve, iterations_per_start, max_cuts, threads)
    result.context = ctx

    executor = None
    if jobs > 1:
        # "spawn" works the same on Linux, Windows and macOS, and keeps OR-Tools' threads out of forked children.
        executor = concurrent.futures.ProcessPoolExecutor(
            jobs, mp_context=multiprocessing.get_context("spawn"), initializer=_worker_init, initargs=(ctx,))
    try:
        if executor is None:
            _threads = threads
            outcomes = [_run_start(ctx, *args, log=log) for args in starts]
        else:
            outcomes = list(executor.map(_worker_start, starts))
            for outcome in outcomes:
                for line in outcome.lines:
                    log(line)
        closest: Design | None = None
        finished: list[Design] = []
        for outcome in outcomes:
            result.iterations += outcome.iterations
            result.capped_solves += outcome.capped
            result.starts.append((outcome.label, outcome.best.score if outcome.best else None))
            if outcome.best is not None:
                finished.append(outcome.best)
            c = outcome.closest
            if c is not None and (closest is None or len(c.failed) < len(closest.failed)):
                closest = c

        if finished:
            # Polish the best starts' designs: the exact local search often moves a weaker start past a stronger
            # one. Waves of `jobs` designs share the polish time.
            unique = {tuple(sorted(d.outfits.items())): d for d in sorted(finished, key=lambda d: d.score)}
            queue = sorted(unique.values(), key=lambda d: -d.score)[:max(POLISH_DESIGNS, jobs)]
            waves = math.ceil(len(queue) / jobs)
            share = polish_seconds / waves
            if executor is None:
                polished = [_run_polish(ctx, d, share) for d in queue]
            else:
                polished = list(executor.map(_worker_polish, [(d, share) for d in queue]))
            best, best_moves = None, 0
            for design, (done, moves) in zip(queue, polished):
                log(f"polish {design.start}: {design.score:.3f} → {done.score:.3f} ({moves} moves)")
                if best is None or done.score > best.score:
                    best, best_moves = done, moves
            result.status, result.design, result.polish_moves = "optimized", best, best_moves
        else:
            result.status, result.closest = "no design passed the checks", closest
            if closest:
                result.blockers = sorted({c.name for c in closest.failed})
    finally:
        if executor is not None:
            executor.shutdown()
    result.seconds = time.monotonic() - start
    return result


def polish(game: GameData, hull: Hull, pool: list[Outfit], bounds: dict[str, int], design: Design, judge,
           deadline: float) -> tuple[Design, int]:
    """Exact local search with the calculator, keeping every check passing.

    First strip: remove any single outfit whose removal doesn't lower the score. Then take the best move of: add
    one, remove one, remove two different ones (an Outfits Expansion and the Cargo Expansion that makes up its cargo
    space), swap one out for one or two of another, or swap several of one out for one or two of a substitute (an
    outfit providing something the removed one provides: several small heat shunts for a large one). A move must
    raise the score, or keep it and use less space (see WASTE_PENALTY). Repeat until no move helps or time runs
    out, then strip again."""
    names = [o.name for o in pool]
    provides = {o.name: {k for k, v in o.attributes.items() if v > 0} for o in pool}
    moves = 0

    def better(candidate: Design, than: Design) -> bool:
        if candidate.failed:
            return False
        if candidate.score > than.score + 1e-9:
            return True
        return (candidate.score > than.score - 1e-9
                and design_waste(game, candidate.outfits) < design_waste(game, than.outfits) - 1e-9)

    def trial(outfits: dict[str, int]) -> Design | None:
        ship = calculator.build(game, hull, outfits)
        return None if ship.fit_errors else judge(outfits, ship)

    def strip(current: Design, moves: int) -> tuple[Design, int]:
        stripped = True
        while stripped and time.monotonic() < deadline:
            stripped = False
            for a in sorted(current.outfits, key=lambda n: -waste(game.outfits[n])):
                candidate = trial({**current.outfits, a: current.outfits[a] - 1})
                if candidate is not None and not candidate.failed and candidate.score >= current.score - 1e-9:
                    current, moves, stripped = candidate, moves + 1, True
                    break
        return current, moves

    current, moves = strip(design, moves)

    while time.monotonic() < deadline:
        out = current.outfits
        trials: list[dict[str, int]] = []
        for a in out:
            trials.append({**out, a: out[a] - 1})
        installed = sorted(out)
        for i, a in enumerate(installed):
            for b in installed[i + 1:]:
                trials.append({**out, a: out[a] - 1, b: out[b] - 1})
        for n in names:
            if out.get(n, 0) < bounds[n]:
                trials.append({**out, n: out.get(n, 0) + 1})
        for a in out:
            for b in names:
                if b == a:
                    continue
                substitute = bool(provides.get(a, set()) & provides[b])
                for k in range(1, (out[a] if substitute else 1) + 1):
                    for m in (1, 2):
                        if out.get(b, 0) + m <= bounds[b]:
                            trials.append({**out, a: out[a] - k, b: out.get(b, 0) + m})
        best = None
        for outfits in trials:
            if time.monotonic() > deadline:
                break
            candidate = trial(outfits)
            if candidate is not None and better(candidate, best or current):
                best = candidate
        if best is None:
            break
        current, moves = best, moves + 1
    deadline = max(deadline, time.monotonic() + 5)      # the final strip always gets a few seconds
    return strip(current, moves)


def _blockers(model: _Model, seconds: float) -> list[str]:
    """Requirement groups that, switched off alone, make a design possible."""
    names = list(model.groups)
    found = [g for g in names if model.solve(seconds, enabled=set(names) - {g}) is not None]
    return found or ["several requirements together (no single one is the cause)"]
