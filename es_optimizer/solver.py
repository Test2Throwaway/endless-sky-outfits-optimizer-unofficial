"""Optimizer: choose outfit counts for one hull that best fit a design request.

Method (see docs/design-notes.md):

- One integer count per candidate outfit, solved with OR-Tools CP-SAT.
- The game's fit rule and the energy and heat scenarios are linear constraints. Values that depend on the
  design itself (mass in acceleration, agility in weapon value, cooling efficiency, ...) are linearized around
  the current design and re-solved until the design stops changing.
- Every design the solver returns is re-checked with the calculator, which matches the game. A design that
  fails a hard check is excluded and the solver tries again.
- Each weighted metric is scored against the best this hull reaches for that metric alone.
- If no design exists, each requirement group is switched off in turn to find what blocks it.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from . import calculator, roles
from .availability import Availability
from .calculator import Check, Role, Ship
from .gamedata import GameData, Hull, Outfit
from .storage import Settings

SCALE = 10_000            # attributes have 4 decimal places in the game
OBJECTIVE_SCALE = 1_000_000
# Never used in designs: hand-to-hand gear gets no weight (illegal-boarding roles will add Nerve Gas, one per
# bunk, separately), and licences and minerals aren't installable.
NOT_INSTALLABLE = ("Licenses", "Minerals", "Hand to Hand")


@dataclass
class Design:
    outfits: dict[str, int]
    ship: Ship
    checks: list[Check]
    metrics: dict[str, float]
    score: float

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
    ideals: dict[str, float] = field(default_factory=dict)
    iterations: int = 0
    seconds: float = 0.0
    candidates: int = 0


# --- Candidate outfits ---

def candidates(game: GameData, hull: Hull, settings: Settings, request: roles.Request) -> list[Outfit]:
    available = Availability(game, settings)
    pool = []
    for o in game.outfits.values():
        if not o.category or o.category in NOT_INSTALLABLE or o.attributes.get("installable", 0) < 0:
            continue
        if not available.outfit_ok(o) or not request.outfit_allowed(game, o):
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
                    ideals: dict[str, float], disruption: bool, targets: list[Ship] | None) -> Design:
    ship = calculator.build(game, hull, outfits)
    checks = roles.check_request(ship, request, game) + calculator.evaluate(ship, request.role, disruption, targets)
    metrics = {m: roles.metric_value(ship, request.role, m) for m in request.weights}
    score = sum(w * metrics[m] / ideals[m] for m, w in request.weights.items() if ideals.get(m))
    return Design({k: v for k, v in outfits.items() if v}, ship, checks, metrics, score)


# --- The linear model ---

class _Model:
    """CP-SAT model of the request, linearized around a design `point`."""

    def __init__(self, game: GameData, hull: Hull, pool: list[Outfit], bounds: dict[str, int],
                 request: roles.Request, point: Ship, cuts: list[dict[str, int]]):
        self.game, self.hull, self.pool, self.request, self.point = game, hull, pool, request, point
        self.role: Role = request.role
        self.m = cp_model.CpModel()
        self.bounds = bounds
        self.x = {o.name: self.m.NewIntVar(0, bounds[o.name], o.name) for o in pool}
        self.zero = self.m.NewIntVar(0, 0, "zero")       # keeps every expression a CP-SAT expression
        self.groups: dict[str, cp_model.IntVar] = {}
        self.weapon_unit = {o.name: calculator._weapon_stats(game, o, 1) for o in pool if o.weapon is not None}
        self._build()
        for cut in cuts:
            self._exclude(cut)

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
                t = calculator.TORCH_THRUST_SHARE
                m.Add(worst_e * 100 >= round(t * 100) * moves["thrust"][0] + round((1 - t) * 100) * rest_e)
                m.Add(worst_h * 100 >= round(t * 100) * moves["thrust"][1] + round((1 - t) * 100) * rest_h)
            else:
                for energy, heat in moves.values():
                    m.Add(worst_e >= energy)
                    m.Add(worst_h >= heat)
            weapons_e = self.per_outfit({n: v * share for n, v in w_energy.items()})
            weapons_h = self.per_outfit({n: v * share for n, v in w_heat.items()})
            return weapons_e + worst_e, weapons_h + worst_h

        share = 1.0 if role.combat and not fighter_rules else calculator.WEAPON_SHARE_NON_COMBAT
        if interceptor:
            load_e, load_h = load(calculator.WEAPON_SHARE_NON_COMBAT)
            f = calculator.SOLAR_COMBAT
            frames = calculator.INTERCEPTOR_BATTLE_FRAMES
            drain = load_e + cooling_draw - idle_energy - self.attr("solar collection", f * solar_on)
            self.require("interceptor reserves", drain * frames <= self.attr("energy capacity"))
            heat_ok("interceptor reserves", idle_heat + load_h + self.attr("solar heat", f))   # conservative
        else:
            load_e, load_h = load(share)
            f = calculator.SOLAR_COMBAT
            heat_ok("combat heat", idle_heat + load_h + self.attr("solar heat", f))
            self.require("combat energy",
                         idle_energy + self.attr("solar collection", f * solar_on) - load_e - cooling_draw >= 0)
        f = calculator.SOLAR_STAY
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
            burn = self.attr("thrusting fuel", calculator.TORCH_THRUST_SHARE * role.fight_seconds * calculator.FPS)
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

    def _regen(self, o: Outfit, resource: str) -> float:
        p = self.point
        value = 0.0
        for kind in ("shield", "hull"):
            base = o.attributes.get(f"{kind} {resource}", 0.0) + o.attributes.get(f"delayed {kind} {resource}", 0.0)
            value += base * (1 + p.get(f"{kind} {resource} multiplier"))
        return value

    # solving
    def set_objective(self, weights: dict[str, float], ideals: dict[str, float]) -> None:
        total = {}
        for metric, weight in weights.items():
            if not weight or not ideals.get(metric):
                continue
            values, _ = self.linear_metric(metric)
            for name, v in values.items():
                total[name] = total.get(name, 0.0) + weight * v / ideals[metric]
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
        solver.parameters.num_workers = 8
        self.m.ClearAssumptions()
        self.m.AddAssumptions(assumptions + [lit.Not() for lit in off])
        status = solver.Solve(self.m)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return {n: solver.Value(v) for n, v in self.x.items() if solver.Value(v)}


# --- Driver ---

def optimize(game: GameData, hull: Hull, request: roles.Request, settings: Settings,
             seconds_per_solve: float = 10.0, max_iterations: int = 8, max_cuts: int = 20,
             capture_targets: list[Ship] | None = None) -> Result:
    start = time.monotonic()
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

    # Is there any design at all? If not, find what blocks it.
    model = _Model(game, hull, pool, bounds, request, empty, [])
    first = model.solve(seconds_per_solve)
    if first is None:
        result.blockers = _blockers(model, seconds_per_solve)
        result.seconds = time.monotonic() - start
        return result

    # Ideal value of each weighted metric: the best this hull reaches for that metric alone.
    ideals: dict[str, float] = {}
    for metric, weight in request.weights.items():
        point = calculator.build(game, hull, first)
        best = 0.0
        for _ in range(2):
            model = _Model(game, hull, pool, bounds, request, point, [])
            model.set_objective({metric: 1.0}, {metric: 1.0})
            found = model.solve(seconds_per_solve, hint=point.outfits) or first
            point = calculator.build(game, hull, found)
            best = max(best, roles.metric_value(point, request.role, metric))
        ideals[metric] = best if best > 0 else 1.0
    result.ideals = ideals

    # Main loop: linearize, solve, check with the calculator, repeat.
    cuts: list[dict[str, int]] = []
    point = calculator.build(game, hull, first)
    seen: list[dict[str, int]] = []
    best_design: Design | None = None
    closest: Design | None = None
    for iteration in range(max_iterations + max_cuts):
        result.iterations = iteration + 1
        model = _Model(game, hull, pool, bounds, request, point, cuts)
        model.set_objective(request.weights, ideals)
        found = model.solve(seconds_per_solve, hint=point.outfits)
        if found is None:
            found = model.solve(seconds_per_solve * 3, hint=point.outfits)
        if found is None:
            break
        design = evaluate_design(game, hull, found, request, ideals, disruption, capture_targets)
        for m, v in design.metrics.items():           # keep normalization honest
            if v > ideals.get(m, 0):
                ideals[m] = v
        if design.failed:
            if closest is None or len(design.failed) < len(closest.failed):
                closest = design
            cuts.append(found)
            if len(cuts) > max_cuts:
                break
            continue
        if best_design is None or design.score > best_design.score:
            best_design = design
        if found in seen:
            break
        seen.append(found)
        point = design.ship
        if len(seen) >= max_iterations:
            break

    if best_design is not None:
        # Rescore with the final ideals.
        best_design = evaluate_design(game, hull, best_design.outfits, request, ideals, disruption, capture_targets)
        result.status, result.design = "optimized", best_design
    else:
        result.status, result.closest = "no design passed the checks", closest
        if closest:
            result.blockers = sorted({c.name for c in closest.failed})
    result.seconds = time.monotonic() - start
    return result


def _blockers(model: _Model, seconds: float) -> list[str]:
    """Requirement groups that, switched off alone, make a design possible."""
    names = list(model.groups)
    found = [g for g in names if model.solve(seconds, enabled=set(names) - {g}) is not None]
    return found or ["several requirements together (no single one is the cause)"]
