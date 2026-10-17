"""Role specs: what a ship is for, as TOML files with must / should / may sections.

A design request combines one to three roles. See docs/roles.md for the format.
"""

from __future__ import annotations

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
    "weapon value": (lambda s, r: 60 * sum(s.weapon_value(w, r.goal, fight_seconds=r.fight_seconds)
                                           for w in s.weapons),
                     "damage per second weighted by the goal, after range, fixed-gun and magazine-window factors"),
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
    "needs_anti_missile": bool, "capture_targets": list,
}
FIGHTS = {"escort": 90.0, "dedicated": 240.0}


@dataclass
class RoleSpec:
    name: str
    description: str = ""
    ship: dict = field(default_factory=dict)
    must_min: dict[str, float] = field(default_factory=dict)
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
    composites: dict[str, dict[str, float]] = field(default_factory=dict)
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
    if ship.get("goal", "normal") not in calculator.GOALS:
        raise RoleError(f"{where}: goal must be one of {', '.join(calculator.GOALS)}")
    if ship.get("fight", "dedicated") not in FIGHTS:
        raise RoleError(f"{where}: fight must be one of {', '.join(FIGHTS)}")

    must, may, outfits = table("must"), table("may"), table("outfits")
    unknown = set(must) - {"min", "max", "has", "reverse_thrust", "emphasize"}
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
    composites = {k: {m: float(w) for m, w in v.items()} for k, v in table("metrics").items()}
    return RoleSpec(
        name=data.get("name", name), description=data.get("description", ""), ship=ship,
        must_min={k: float(v) for k, v in must.get("min", {}).items()},
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


def shared_metrics(home: Path | None) -> dict[str, dict[str, float]]:
    """Composite metric definitions from _metrics.toml (bundled, then the user's)."""
    composites: dict[str, dict[str, float]] = {}
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
class Request:
    roles: list[RoleSpec]
    role: Role                              # calculator settings
    must_min: dict[str, float]
    must_max: dict[str, float]
    must_have: list[str]
    must_not: list[str]
    reverse_thrust: str | None
    # Primitive metric -> weight, after expanding composites; role weights are normalized so each role counts equally.
    weights: dict[str, float]
    allow_tags: set[str]
    forbid_tags: set[str]
    capture_targets: list[str]

    def outfit_allowed(self, game: GameData, outfit: Outfit) -> bool:
        """The [outfits] section: forbidden tags exclude an outfit unless one of its tags is explicitly allowed."""
        tags = outfit_tags(game, outfit)
        return not (tags & self.forbid_tags) or bool(tags & self.allow_tags)


def combine(roles: list[RoleSpec], composites: dict[str, dict[str, float]], game: GameData | None = None) -> Request:
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
        needs_anti_missile=all_need("needs_anti_missile"),
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
    def expand(name: str) -> dict[str, float]:
        parts = all_composites.get(name, {name: 1.0})
        total = sum(parts.values()) or 1.0
        return {m: w / total for m, w in parts.items()}

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

    deprioritized = {m for r in roles for name in r.deprioritize for m in all_composites.get(name, {name: 1.0})}
    for metric in deprioritized & set(weights):
        if weights[metric] > 0:
            weights[metric] *= DEPRIORITIZE_FACTOR
    size = sum(abs(v) for v in weights.values()) or 1.0
    weights = {m: v / size for m, v in weights.items()}
    for metric in list(weights) + list(must_min) + list(must_max) + must_have + must_not:
        if not known_metric(metric, game):
            raise RoleError(f"Unknown metric or attribute '{metric}'. Known metrics: {', '.join(METRICS)}; "
                            "composites: " + ", ".join(sorted(all_composites)) + "; or any outfit attribute name.")
    targets = sorted({t for s in ship for t in s.get("capture_targets", [])})
    return Request(roles, role, must_min, must_max, must_have, must_not, reverse_thrust, weights,
                   {t for r in roles for t in r.allow_tags}, {t for r in roles for t in r.forbid_tags}, targets)


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
