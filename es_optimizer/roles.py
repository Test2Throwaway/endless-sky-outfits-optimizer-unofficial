"""Role specs: what a ship is for, as TOML files with must / should / may sections.

A design request combines one to three roles. See docs/roles.md for the format.
"""

from __future__ import annotations

import itertools
import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import calculator
from .calculator import Role, Ship
from .gamedata import GameData, Outfit

BUNDLED_DIR = Path(__file__).parent / "roles"
REVERSE_LEVELS = ["none", "useless", "useful", "balanced", "nimble"]
# Outfit tags: hit force at least this many times the damage makes a weapon a push or pull weapon.
PUSH_FORCE_PER_DAMAGE = 2.0
PULL_FORCE_PER_DAMAGE = 1.0
# Weights are built in steps. [should] sets the baseline (scaled to 100%). Each later step gives its metrics a
# fixed share of the score and scales everything before it to make room, so a step's strength does not depend on
# how many items earlier sections have. A number given for an item in these sections is its own share.
MUST_EMPHASIS = 0.5     # [must] emphasize: 50% between them
MAY_BONUS = 0.1         # [may] bonus: 10%
SHOULD_NOT_PENALTY = 0.2  # [should_not]: −20%
# [should] deprioritize: the metric's combined weight is multiplied by this.
DEPRIORITIZE_FACTOR = 0.1
# [must_not] entries that switch off a default requirement.
DEFAULT_OVERRIDES = {"anti-missile": "needs_anti_missile", "ramscoop": "needs_ramscoop"}
DRIVES = ("hyperdrive", "jump drive", "quantum keystone")


class RoleError(ValueError):
    pass


# --- Metrics: named numbers the calculator can produce for a design ---

METRICS: dict[str, tuple[Callable[[Ship, Role], float], str]] = {
    "max speed": (lambda s, r: s.max_speed, "top speed, as shown in game"),
    "acceleration": (lambda s, r: s.acceleration, "as shown in game"),
    "reverse acceleration": (lambda s, r: s.reverse_acceleration, "as shown in game"),
    "turn rate": (lambda s, r: s.turn_rate, "degrees per second"),
    "agility": (lambda s, r: s.agility, "equivalent turn, combining turn and acceleration"),
    "effective shields": (lambda s, r: s.effective_shields, "max shields × (1 + shield protection)"),
    "effective hull": (lambda s, r: s.effective_hull, "max hull × (1 + hull protection)"),
    "shield regen": (lambda s, r: s.shield_regen * 60 * (1 + s.get("shield protection")),
                     "effective shield regeneration per second"),
    "hull repair": (lambda s, r: s.hull_repair * 60 * (1 + s.get("hull protection")),
                    "effective hull repair per second"),
    "weapon value": (lambda s, r: 60 * sum(s.weapon_value(w, r.goal, fight_seconds=r.fight_seconds,
                                                          combat=r.combat, reference=r.reference_weapons,
                                                          reference_agility=r.stock_agility.get(s.hull.name))
                                           for w in s.weapons),
                     "damage per second weighted by the goal and by how well each weapon suits the ship, relative "
                     "to the average available weapon (range, fixed guns, fire rate, turret turn, projectile speed, "
                     "magazine window)"),
    "shield dps": (lambda s, r: 60 * sum(w.shield_damage for w in s.weapons if w.offensive), "per second"),
    "hull dps": (lambda s, r: 60 * sum(w.hull_damage for w in s.weapons if w.offensive), "per second"),
    "anti-missile": (lambda s, r: sum(w.anti_missile * w.count for w in s.weapons if w.anti_missile),
                     "anti-missile strength summed over turrets"),
    "tractor beam": (lambda s, r: sum(w.tractor * w.count for w in s.weapons if w.tractor),
                     "tractor beam strength summed over turrets"),
    "push force": (lambda s, r: 60 * sum(w.hit_force for w in s.weapons if w.hit_force > 0), "per second"),
    "pull force": (lambda s, r: -60 * sum(w.hit_force for w in s.weapons if w.hit_force < 0), "per second"),
    "jumps": (lambda s, r: float(s.jumps), "jumps of fuel at the average fuel per jump"),
    "free outfit space": (lambda s, r: s.get("outfit space"), "outfit space left unused"),
}


def metric_value(ship: Ship, role: Role, name: str) -> float:
    if name in METRICS:
        return METRICS[name][0](ship, role)
    return ship.get(name)          # any outfit or hull attribute, totalled over the ship


def known_metric(name: str, game: GameData | None) -> bool:
    if name in METRICS:
        return True
    if game is None:
        return True
    return any(name in o.attributes for o in game.outfits.values()) or any(
        name in h.attributes for h in game.hulls.values())


# --- Outfit tags, for the may section ---

def outfit_tags(game: GameData, outfit: Outfit) -> set[str]:
    tags: set[str] = set()
    a = outfit.attributes
    if outfit.weapon is not None:
        w = calculator._weapon_stats(game, outfit, 1)
        damage = w.shield_damage + w.hull_damage
        if w.offensive:
            tags.add("damage weapon")
        if w.anti_missile:
            tags.add("anti-missile")
        if w.tractor:
            tags.add("tractor beam")
        if w.hit_force > 0 and (damage == 0 or w.hit_force >= PUSH_FORCE_PER_DAMAGE * damage):
            tags.add("push weapon")
        if w.hit_force < 0 and (damage == 0 or -w.hit_force >= PULL_FORCE_PER_DAMAGE * damage):
            tags.add("pull weapon")
        if w.instantaneous:
            tags.add("instantaneous")
        if w.disruption:
            tags.add("shield disruption")
        if outfit.weapon.stats.get("missile strength", 0) > 0:
            tags.add("missile")
        if w.fuel:
            tags.add("fuel weapon")
    if a.get("afterburner thrust"):
        tags.add("afterburner")
    if a.get("cloak"):
        tags.add("cloak")
    if a.get("illegal"):
        tags.add("illegal")
    if a.get("solar collection"):
        tags.add("solar")
    if a.get("ramscoop"):
        tags.add("ramscoop")
    if a.get("thrusting fuel", 0) > 0:
        tags.add("torch")
    return tags


ALL_TAGS = ["damage weapon", "anti-missile", "tractor beam", "push weapon", "pull weapon", "instantaneous",
            "shield disruption", "missile", "fuel weapon", "afterburner", "cloak", "illegal", "solar", "ramscoop",
            "torch"]


# --- Role files ---

SHIP_KEYS = {
    "combat": bool, "fighter": bool, "hero": bool, "goal": str, "fight": str, "evader": bool,
    "must_run_dark": bool, "long_range": bool, "fights_per_restock": int, "needs_ramscoop": bool, "needs_drives": bool,
    "needs_anti_missile": bool, "capture_targets": list, "weapons_budget": list, "engines_budget": list,
    "unique_outfits": bool, "needs_regen": bool,
}
FIGHTS = {"escort": 90.0, "dedicated": 240.0}
# Budget ranges: the share of the hull's weapon and engine capacity the optimizer may hand to weapons and engines.
# Starting designs are spread over these ranges (see solver). Roles narrow them in [ship].
DEFAULT_WEAPONS_BUDGET = (0.0, 1.0)
DEFAULT_ENGINES_BUDGET = (0.4, 1.0)
# Product composites: a part scoring 0 would make the whole 0 and its slope infinite; linearization floors part
# scores at this.
PRODUCT_FLOOR = 0.02
# A "best of" composite has one route per branch; requests with several of them get every combination, up to this.
MAX_ROUTES = 8


@dataclass
class RoleSpec:
    name: str
    description: str = ""
    ship: dict = field(default_factory=dict)
    must_min: dict[str, float] = field(default_factory=dict)
    # Metric -> share of stock ships (with a non-zero value) the design must at least match, e.g. 0.05.
    must_percentile: dict[str, float] = field(default_factory=dict)
    must_max: dict[str, float] = field(default_factory=dict)
    must_have: list[str] = field(default_factory=list)
    reverse_thrust: str | None = None
    should: dict[str, float] = field(default_factory=dict)
    # Metric -> weight, or None for the default factor.
    emphasize: dict[str, float | None] = field(default_factory=dict)
    may: dict[str, float | None] = field(default_factory=dict)
    must_not: list[str] = field(default_factory=list)
    should_not: dict[str, float | None] = field(default_factory=dict)
    deprioritize: list[str] = field(default_factory=list)
    allow_tags: list[str] = field(default_factory=list)
    forbid_tags: list[str] = field(default_factory=list)
    # Composite name -> {metric: weight}, {"best_of": [composite or metric, ...]}, or {"product": {metric: weight}}.
    composites: dict[str, dict] = field(default_factory=dict)
    source: str = ""


def parse_role(text: str, name: str, source: str = "") -> RoleSpec:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise RoleError(f"{source or name}: {error}") from None
    where = source or name

    def table(key: str) -> dict:
        value = data.get(key, {})
        if not isinstance(value, dict):
            raise RoleError(f"{where}: [{key}] must be a table")
        return value

    unknown = set(data) - {"name", "description", "ship", "must", "must_not", "should", "should_not", "may",
                           "outfits", "metrics"}
    if unknown:
        raise RoleError(f"{where}: unknown section(s): {', '.join(sorted(unknown))}")
    ship = table("ship")
    for key, value in ship.items():
        if key not in SHIP_KEYS:
            raise RoleError(f"{where}: unknown [ship] setting '{key}' (known: {', '.join(SHIP_KEYS)})")
        if not isinstance(value, SHIP_KEYS[key]):
            raise RoleError(f"{where}: [ship] {key} must be a {SHIP_KEYS[key].__name__}")
        if key.endswith("_budget") and not (len(value) == 2 and all(isinstance(v, (int, float)) for v in value)
                                             and 0 <= value[0] <= value[1] <= 1):
            raise RoleError(f"{where}: [ship] {key} must be [low, high] with 0 ≤ low ≤ high ≤ 1")
    if ship.get("goal", "normal") not in calculator.GOALS:
        raise RoleError(f"{where}: goal must be one of {', '.join(calculator.GOALS)}")
    if ship.get("fight", "dedicated") not in FIGHTS:
        raise RoleError(f"{where}: fight must be one of {', '.join(FIGHTS)}")

    must, may, outfits = table("must"), table("may"), table("outfits")
    unknown = set(must) - {"min", "max", "has", "reverse_thrust", "emphasize", "min_percentile"}
    if unknown:
        raise RoleError(f"{where}: unknown [must] key(s): {', '.join(sorted(unknown))}")
    unknown = set(may) - {"bonus"}
    if unknown:
        raise RoleError(f"{where}: unknown [may] key(s): {', '.join(sorted(unknown))} "
                        "(use bonus = [...]; outfit tags go in [outfits])")
    unknown = set(outfits) - {"allow", "forbid"}
    if unknown:
        raise RoleError(f"{where}: unknown [outfits] key(s): {', '.join(sorted(unknown))}")
    must_not, should_not = table("must_not"), table("should_not")
    unknown = set(must_not) - {"have"}
    if unknown:
        raise RoleError(f"{where}: unknown [must_not] key(s): {', '.join(sorted(unknown))} (use have = [...])")
    unknown = set(should_not) - {"have"}
    if unknown:
        raise RoleError(f"{where}: unknown [should_not] key(s): {', '.join(sorted(unknown))} (use have = [...])")

    def weighted(value, key: str) -> dict[str, float | None]:
        if isinstance(value, list):
            return {m: None for m in value}
        if isinstance(value, dict):
            return {m: float(w) for m, w in value.items()}
        raise RoleError(f"{where}: {key} must be a list of metrics or a table of metric = weight")
    for k, v in must.get("min_percentile", {}).items():
        if not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise RoleError(f"{where}: [must] min_percentile for {k} must be a share between 0 and 1")
    reverse = must.get("reverse_thrust")
    if reverse is not None and reverse not in REVERSE_LEVELS[2:]:
        raise RoleError(f"{where}: reverse_thrust must be one of {', '.join(REVERSE_LEVELS[2:])}")
    for tag in list(outfits.get("allow", [])) + list(outfits.get("forbid", [])):
        if tag not in ALL_TAGS:
            raise RoleError(f"{where}: unknown tag '{tag}' (known: {', '.join(ALL_TAGS)})")
    should_table = dict(table("should"))
    deprioritize = should_table.pop("deprioritize", [])
    if not isinstance(deprioritize, list):
        raise RoleError(f"{where}: [should] deprioritize must be a list of metrics")
    should = {k: float(v) for k, v in should_table.items()}
    if any(v < 0 for v in should.values()):
        raise RoleError(f"{where}: [should] weights must be zero or positive")
    composites: dict[str, dict] = {}
    for k, v in table("metrics").items():
        if not isinstance(v, dict):
            raise RoleError(f"{where}: [metrics.{k}] must be a table")
        if v.get("combine", "sum") not in ("sum", "product"):
            raise RoleError(f"{where}: [metrics.{k}] combine must be \"sum\" or \"product\"")
        if v.get("combine") == "product":
            parts = {m: w for m, w in v.items() if m != "combine"}
            if len(parts) < 2 or not all(isinstance(w, (int, float)) and w > 0 for w in parts.values()):
                raise RoleError(f"{where}: [metrics.{k}] a product needs two or more metrics with positive weights")
            composites[k] = {"product": {m: float(w) for m, w in parts.items()}}
        elif "best_of" in v:
            if set(v) != {"best_of"} or not isinstance(v["best_of"], list) or len(v["best_of"]) < 2:
                raise RoleError(f"{where}: [metrics.{k}] best_of must be a list of two or more metrics, "
                                "and nothing else")
            composites[k] = {"best_of": [str(b) for b in v["best_of"]]}
        else:
            composites[k] = {m: float(w) for m, w in v.items() if m not in ("combine", "when_chosen")}
        if "when_chosen" in v:
            effects = v["when_chosen"]
            if not isinstance(effects, dict) or set(effects) - {"scale", "bonus"}:
                raise RoleError(f"{where}: [metrics.{k}] when_chosen takes scale = {{...}} and bonus = {{...}}")
            composites[k]["when_chosen"] = {kind: {m: float(x) for m, x in effects.get(kind, {}).items()}
                                            for kind in ("scale", "bonus")}
    return RoleSpec(
        name=data.get("name", name), description=data.get("description", ""), ship=ship,
        must_min={k: float(v) for k, v in must.get("min", {}).items()},
        must_percentile={k: float(v) for k, v in must.get("min_percentile", {}).items()},
        must_max={k: float(v) for k, v in must.get("max", {}).items()},
        must_have=list(must.get("has", [])), reverse_thrust=reverse, should=should,
        emphasize=weighted(must.get("emphasize", []), "[must] emphasize"),
        may=weighted(may.get("bonus", []), "[may] bonus"),
        allow_tags=list(outfits.get("allow", [])), forbid_tags=list(outfits.get("forbid", [])),
        must_not=list(must_not.get("have", [])),
        should_not=weighted(should_not.get("have", []), "[should_not] have"), deprioritize=list(deprioritize),
        composites=composites, source=source)


def role_dirs(home: Path | None) -> list[Path]:
    """Bundled roles first, then the user's own roles, which override bundled ones of the same file name."""
    return [BUNDLED_DIR] + ([Path(home) / "roles"] if home else [])


def available_roles(home: Path | None) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for folder in role_dirs(home):
        if folder.is_dir():
            for path in sorted(folder.glob("*.toml")):
                if not path.name.startswith("_"):
                    found[path.stem] = path
    return found


def shared_metrics(home: Path | None) -> dict[str, dict]:
    """Composite metric definitions from _metrics.toml (bundled, then the user's)."""
    composites: dict[str, dict] = {}
    for folder in role_dirs(home):
        path = folder / "_metrics.toml"
        if path.exists():
            composites.update(parse_role(path.read_text(encoding="utf-8"), "_metrics", str(path)).composites)
    return composites


def load_role(name_or_path: str, home: Path | None) -> RoleSpec:
    path = Path(name_or_path)
    if not path.suffix:
        roles = available_roles(home)
        if name_or_path not in roles:
            raise RoleError(f"No role named '{name_or_path}' (available: {', '.join(sorted(roles)) or 'none'})")
        path = roles[name_or_path]
    if not path.exists():
        raise RoleError(f"No role file {path}")
    return parse_role(path.read_text(encoding="utf-8"), path.stem, str(path))


# --- Combining roles into one design request ---

@dataclass
class Route:
    """One way to score a design: a choice of branch for every "best of" composite, and the weights it gives."""
    label: str                      # e.g. "survivability: durable"; "" when there are no choices
    weights: dict[str, float]


@dataclass
class Request:
    roles: list[RoleSpec]
    role: Role                              # calculator settings
    must_min: dict[str, float]
    must_max: dict[str, float]
    must_have: list[str]
    must_not: list[str]
    reverse_thrust: str | None
    # Primitive metric -> weight, after expanding composites; role weights are normalized so each role counts equally.
    # This is the first route's; a design's score is its best over all routes.
    weights: dict[str, float]
    allow_tags: set[str]
    forbid_tags: set[str]
    capture_targets: list[str]
    routes: list[Route] = field(default_factory=list)
    # Metric -> share of stock ships to match; turned into must_min by solver.resolve_percentiles.
    must_percentile: dict[str, float] = field(default_factory=dict)
    # Product composites used in the weights: name -> {metric: weight}. Scored as the weighted geometric mean of
    # the parts' scores, so a design must be good at all of them; the weights are the exponents.
    products: dict[str, dict[str, float]] = field(default_factory=dict)
    # Outfits marked unique (story items, one of a kind): by default only for the ship you fly yourself.
    unique_outfits: bool = False
    weapons_budget: tuple[float, float] = DEFAULT_WEAPONS_BUDGET
    engines_budget: tuple[float, float] = DEFAULT_ENGINES_BUDGET

    @property
    def metrics(self) -> list[str]:
        """Every metric any route weighs."""
        seen: dict[str, None] = {}
        for route in self.routes or [Route("", self.weights)]:
            for name in route.weights:
                seen.update(dict.fromkeys(self.products.get(name, [name])))
        return list(seen)

    def outfit_allowed(self, game: GameData, outfit: Outfit) -> bool:
        """The [outfits] section: forbidden tags exclude an outfit unless one of its tags is explicitly allowed."""
        if not self.forbid_tags:
            return True
        cache = self.__dict__.setdefault("_allowed", {})
        if outfit.name not in cache:
            tags = outfit_tags(game, outfit)
            cache[outfit.name] = not (tags & self.forbid_tags) or bool(tags & self.allow_tags)
        return cache[outfit.name]


def combine(roles: list[RoleSpec], composites: dict[str, dict], game: GameData | None = None,
            emphasize: list[str] = (), deprioritize: list[str] = ()) -> Request:
    """`emphasize` and `deprioritize` adjust the whole request (e.g. from the command line): emphasized metrics or
    composites share MUST_EMPHASIS of the score after the roles are combined; deprioritized ones are cut to
    DEPRIORITIZE_FACTOR."""
    if not 1 <= len(roles) <= 3:
        raise RoleError("A design combines one to three roles")
    ship = [r.ship for r in roles]
    goals = {s.get("goal", "normal") for s in ship} - {"normal"}
    if len(goals) > 1:
        raise RoleError(f"Roles disagree on the goal: {', '.join(sorted(goals))}")
    any_true = lambda key: any(s.get(key, False) for s in ship)
    must_not = sorted({m for r in roles for m in r.must_not})
    all_need = lambda key: all(s.get(key, True) for s in ship) and not any(
        DEFAULT_OVERRIDES.get(m) == key for m in must_not)
    combat = [s["combat"] for s in ship if "combat" in s]   # roles that don't say are neutral
    role = Role(
        combat=any(combat) if combat else True,
        fighter=any_true("fighter"), hero=any_true("hero"), goal=goals.pop() if goals else "normal",
        fight_seconds=max(FIGHTS[s.get("fight", "dedicated")] for s in ship),
        evader=any_true("evader"), must_run_dark=any_true("must_run_dark"), long_range=any_true("long_range"),
        fights_per_restock=max([s.get("fights_per_restock", 2) for s in ship]),
        needs_ramscoop=all_need("needs_ramscoop"), needs_drives=all_need("needs_drives"),
        needs_anti_missile=all_need("needs_anti_missile"), needs_regen=all_need("needs_regen"),
        excluded_drives=frozenset(m for m in must_not if m in DRIVES))

    must_min: dict[str, float] = {}
    must_max: dict[str, float] = {}
    for r in roles:
        for k, v in r.must_min.items():
            must_min[k] = max(v, must_min.get(k, -math.inf))
        for k, v in r.must_max.items():
            must_max[k] = min(v, must_max.get(k, math.inf))
    for k in set(must_min) & set(must_max):
        if must_min[k] > must_max[k]:
            raise RoleError(f"Roles conflict: {k} must be at least {must_min[k]:g} and at most {must_max[k]:g}")
    must_have = sorted({m for r in roles for m in r.must_have})
    clash = set(must_not) & (set(must_have) | {k for k, v in must_min.items() if v > 0})
    if clash:
        raise RoleError(f"Roles conflict: must have and must not have {', '.join(sorted(clash))}")
    reverse = [r.reverse_thrust for r in roles if r.reverse_thrust]
    reverse_thrust = max(reverse, key=REVERSE_LEVELS.index) if reverse else None

    all_composites = {**composites, **{k: v for r in roles for k, v in r.composites.items()}}
    choice: dict[str, str] = {}             # best_of composite -> branch, for the route being built
    products: dict[str, dict[str, float]] = {}

    def expand(name: str, depth: int = 0) -> dict[str, float]:
        """A metric or composite as primitive metrics with weights summing to 1."""
        if depth > 10:
            raise RoleError(f"Composite '{name}' refers to itself")
        parts = {m: w for m, w in all_composites.get(name, {name: 1.0}).items() if m != "when_chosen"}
        if "product" in parts:
            if any(m in all_composites for m in parts["product"]):
                raise RoleError(f"Product composite '{name}' must combine metrics, not composites")
            products[name] = parts["product"]
            return {name: 1.0}
        if "best_of" in parts:
            parts = {choice[name]: 1.0}
        if set(parts) == {name}:
            return {name: 1.0}
        total = sum(parts.values()) or 1.0
        flat: dict[str, float] = {}
        for part, w in parts.items():
            for metric, sub in expand(part, depth + 1).items():
                flat[metric] = flat.get(metric, 0.0) + w / total * sub
        return flat

    def best_of_used(names, depth: int = 0) -> list[str]:
        found: list[str] = []
        for name in names:
            parts = all_composites.get(name, {})
            if depth > 10 or set(parts) == {name}:
                continue
            if "product" in parts:
                continue
            branches = parts.get("best_of", [m for m in parts if m != "when_chosen"])
            if "best_of" in parts:
                found.append(name)
            found += [b for b in best_of_used(branches, depth + 1) if b not in found]
        return list(dict.fromkeys(found))

    def build_weights() -> dict[str, float]:
        return _weights(roles, expand, all_composites, list(emphasize), list(deprioritize))

    named = [n for r in roles for section in (r.should, r.emphasize, r.may, r.should_not, r.deprioritize)
             for n in section] + list(_shares(emphasize)) + list(deprioritize)
    choosers = best_of_used(named)
    # Explicit emphasis (a role's [must] emphasize, or the request's) is never cut by a route's effects.
    emphasized = set(_shares(emphasize)) | {n for r in roles for n in r.emphasize}
    options = [all_composites[c]["best_of"] for c in choosers]
    routes: list[Route] = []
    for picks in itertools.islice(itertools.product(*options), MAX_ROUTES):
        choice.update(zip(choosers, picks))
        label = ", ".join(f"{c}: {p}" for c, p in zip(choosers, picks))
        routes.append(Route(label, _route_effects(build_weights(), [all_composites[p] for p in picks
                                                                    if p in all_composites], expand, emphasized)))
    weights = routes[0].weights
    explicit_unique = [s["unique_outfits"] for s in ship if "unique_outfits" in s]
    parts = [m for p in products.values() for m in p]
    for metric in [m for route in routes for m in route.weights if m not in products] + parts + list(must_min) + list(must_max) + must_have + must_not:
        if not known_metric(metric, game):
            raise RoleError(f"Unknown metric or attribute '{metric}'. Known metrics: {', '.join(METRICS)}; "
                            "composites: " + ", ".join(sorted(all_composites)) + "; or any outfit attribute name.")
    targets = sorted({t for s in ship for t in s.get("capture_targets", [])})

    def budget(key: str, default: tuple[float, float]) -> tuple[float, float]:
        ranges = [tuple(s[key]) for s in ship if key in s]
        if not ranges:
            return default
        low, high = max(r[0] for r in ranges), min(r[1] for r in ranges)
        if low > high:
            raise RoleError(f"Roles conflict: {key} ranges don't overlap")
        return (float(low), float(high))
    return Request(roles, role, must_min, must_max, must_have, must_not, reverse_thrust, weights,
                   {t for r in roles for t in r.allow_tags}, {t for r in roles for t in r.forbid_tags}, targets,
                   routes, {k: max(r.must_percentile[k] for r in roles if k in r.must_percentile)
                            for r in roles for k in r.must_percentile}, products,
                   any(explicit_unique) if explicit_unique else role.hero,
                   budget("weapons_budget", DEFAULT_WEAPONS_BUDGET), budget("engines_budget", DEFAULT_ENGINES_BUDGET))


def _shares(items) -> dict[str, float | None]:
    """"name" or "name=share" (from the command line) -> {name: share or None}."""
    out: dict[str, float | None] = {}
    for item in items:
        name, _, share = item.partition("=")
        try:
            out[name.strip()] = float(share) if share else None
        except ValueError:
            raise RoleError(f"'{item}': give a metric, or metric=share with a share such as 0.2") from None
    return out


def _route_effects(weights: dict[str, float], branches: list[dict], expand, emphasized: set[str]) -> dict[str, float]:
    """Apply what the chosen branches say about the rest of the design ("when_chosen"): `scale` multiplies the
    weights of the named metrics or composites (unless explicitly emphasized), `bonus` gives each named one that
    share of the score, scaling the rest to make room. Normalized again to Σ|w| = 1."""
    weights = dict(weights)
    for branch in branches:
        effects = branch.get("when_chosen")
        if not effects:
            continue
        for name, factor in effects["scale"].items():
            if name in emphasized:
                continue
            for metric in expand(name):
                if metric in weights:
                    weights[metric] *= factor
        size = sum(abs(v) for v in weights.values()) or 1.0
        weights = {m: v / size for m, v in weights.items()}
        for name, share in effects["bonus"].items():
            weights = {m: v * (1 - share) for m, v in weights.items()}
            for metric, part in expand(name).items():
                weights[metric] = weights.get(metric, 0.0) + share * part
    size = sum(abs(v) for v in weights.values()) or 1.0
    return {m: v / size for m, v in weights.items()}


def _weights(roles: list[RoleSpec], expand, all_composites, emphasize: list[str] = (),
             deprioritize: list[str] = ()) -> dict[str, float]:
    """Each role's weights built step by step, roles counting equally, normalized to Σ|w| = 1; then the request's
    own emphasis and deprioritization."""
    def step(weights: dict[str, float], items: dict[str, float | None], pool: float, sign: float) -> None:
        """Give the listed items a fixed share of the score; scale everything else to make room."""
        if not items:
            return
        default = pool / len(items)
        shares = {name: (w if w is not None else default) for name, w in items.items()}
        claimed = min(1.0, sum(shares.values()))
        added: dict[str, float] = {}
        for name, share in shares.items():
            for metric, part in expand(name).items():
                added[metric] = added.get(metric, 0.0) + sign * share * part
        for metric in list(weights):
            weights[metric] = 0.0 if metric in added else weights[metric] * (1 - claimed)
        for metric, value in added.items():
            weights[metric] = value

    weights: dict[str, float] = {}
    for r in roles:
        role_weights: dict[str, float] = {}
        total = sum(r.should.values())
        for name, w in r.should.items():
            for metric, part in expand(name).items():
                role_weights[metric] = role_weights.get(metric, 0.0) + (w / total if total else 0.0) * part
        step(role_weights, r.emphasize, MUST_EMPHASIS, 1.0)
        step(role_weights, r.may, MAY_BONUS, 1.0)
        step(role_weights, r.should_not, SHOULD_NOT_PENALTY, -1.0)
        size = sum(abs(v) for v in role_weights.values()) or 1.0
        for metric, value in role_weights.items():
            if value:
                weights[metric] = weights.get(metric, 0.0) + value / size / len(roles)

    if emphasize:
        # Each emphasized item gets exactly its share of the score (default: MUST_EMPHASIS between them); everything
        # else keeps its proportions in what is left.
        size = sum(abs(v) for v in weights.values()) or 1.0
        weights = {m: v / size for m, v in weights.items()}
        items = _shares(emphasize)
        default = MUST_EMPHASIS / len(items)
        targets: dict[str, float] = {}
        for name, share in items.items():
            for metric, part in expand(name).items():
                targets[metric] = targets.get(metric, 0.0) + (share if share is not None else default) * part
        rest = sum(abs(v) for m, v in weights.items() if m not in targets) or 1.0
        left = max(0.0, 1.0 - sum(targets.values()))
        weights = {m: v / rest * left for m, v in weights.items() if m not in targets}
        weights.update(targets)
    deprioritized = {m for name in [n for r in roles for n in r.deprioritize] + list(deprioritize)
                     for m in expand(name)}
    for metric in deprioritized & set(weights):
        if weights[metric] > 0:
            weights[metric] *= DEPRIORITIZE_FACTOR
    size = sum(abs(v) for v in weights.values()) or 1.0
    return {m: v / size for m, v in weights.items()}


def check_request(ship: Ship, request: Request, game: GameData) -> list[calculator.Check]:
    """The role's hard requirements and outfit filter, as checks (the rule checks come from calculator.evaluate)."""
    checks: list[calculator.Check] = []
    role = request.role
    for metric, minimum in request.must_min.items():
        value = metric_value(ship, role, metric)
        checks.append(calculator.Check(f"Must: {metric} ≥ {minimum:g}", value >= minimum, f"{value:.4g}"))
    for metric, maximum in request.must_max.items():
        value = metric_value(ship, role, metric)
        checks.append(calculator.Check(f"Must: {metric} ≤ {maximum:g}", value <= maximum, f"{value:.4g}"))
    for metric in request.must_have:
        value = metric_value(ship, role, metric)
        checks.append(calculator.Check(f"Must have: {metric}", value > 0, f"{value:.4g}"))
    for metric in request.must_not:
        value = metric_value(ship, role, metric)
        checks.append(calculator.Check(f"Must not have: {metric}", value <= 0, f"{value:.4g}"))
    if request.reverse_thrust:
        level = reverse_level(ship)
        checks.append(calculator.Check(
            f"Must: reverse thrust {request.reverse_thrust}",
            REVERSE_LEVELS.index(level) >= REVERSE_LEVELS.index(request.reverse_thrust), level))
    disallowed = [n for n in ship.outfits if n in game.outfits and not request.outfit_allowed(game, game.outfits[n])]
    if request.forbid_tags:
        checks.append(calculator.Check("Outfits: none forbidden by tag", not disallowed,
                                       ", ".join(disallowed) if disallowed else "none fitted"))
    return checks


def reverse_level(ship: Ship) -> str:
    t, r, u, d = ship.get("thrust"), ship.get("reverse thrust"), ship.get("turn"), ship.get("drag")
    if not r:
        return "none"
    if not (t and u):
        return "useful"
    useless = t * u / (u + 180 * d) if d else 0.0
    balanced, nimble = u / 60, (u / 60 + t) / 2
    return "useless" if r < useless else "useful" if r < balanced else "balanced" if r < nimble else "nimble"
