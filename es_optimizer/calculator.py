"""Ship calculator: total up a hull plus outfits and check it against the design rules.

Values are per frame unless named otherwise (the game runs 60 frames per second and
displays most rates per second). Formulas follow the game source; see docs/design-notes.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .gamedata import GameData, Hull, Outfit, Weapon

FPS = 60
# Outfit.cpp MINIMUM_OVERRIDES: attributes that may go below 0. None means no minimum.
_ANY_VALUE = [
    "shield energy", "shield fuel", "shield heat", "hull energy", "hull fuel", "hull heat",
    "hull threshold", "energy generation", "energy consumption", "fuel generation",
    "fuel consumption", "fuel energy", "fuel heat", "heat generation", "flotsam chance",
    "cooling energy", "crew equivalent", "cloaking energy", "cloaking fuel", "cloaking heat",
    "cloaking hull", "cloaking repair delay", "cloaking shields", "cloaking shield delay",
    "cloaked firing",
] + [
    f"{mode} {effect}"
    for mode in ("thrusting", "turning", "reverse thrusting", "afterburner")
    for effect in ("shields", "hull", "energy", "fuel", "heat", "discharge", "corrosion", "ion",
                   "leakage", "burn", "disruption", "slowing")
] + [
    f"{kind} resistance {cost}"
    for kind in ("discharge", "corrosion", "ion", "scramble", "leak", "burn", "disruption", "slowing")
    for cost in ("energy", "fuel", "heat")
]
_MINUS_099 = [
    "shield protection", "hull protection", "energy protection", "fuel protection",
    "heat protection", "piercing protection", "force protection", "discharge protection",
    "drag reduction", "corrosion protection", "inertia reduction", "ion protection",
    "scramble protection", "leak protection", "burn protection", "disruption protection",
    "slowing protection",
]
_MINUS_1 = [
    "hull multiplier", "hull repair multiplier", "hull energy multiplier", "hull fuel multiplier",
    "hull heat multiplier", "cloaked repair multiplier", "shield multiplier",
    "shield generation multiplier", "shield energy multiplier", "shield fuel multiplier",
    "shield heat multiplier", "cloaked regen multiplier", "acceleration multiplier",
    "turn multiplier", "turret turn multiplier",
]
MINIMUMS: dict[str, float | None] = {
    **{k: None for k in _ANY_VALUE}, **{k: -0.99 for k in _MINUS_099}, **{k: -1.0 for k in _MINUS_1},
}

# Solar and wind factors (star power or wind × distance factor), from the design notes.
SOLAR_COMBAT = 0.76 * 0.65      # rule 4: 30th-percentile star at 3000
SOLAR_EVADING = 0.70 * 0.50     # rule 3: 20th-percentile star at 5000
SOLAR_STAY = 1.70 * 1.229       # rule 2b: 75th-percentile star at 750
WIND_COMBAT = 0.75 * 0.65       # 30th-percentile wind at 3000
HEAT_TARGET = 0.9               # design target: at or below 90% of max heat
BURST_FRAMES = 150              # 2.5 s of all weapons for non-combat ships
WEAPON_SHARE_NON_COMBAT = 0.5
TORCH_THRUST_SHARE = 0.85
FAST_FORWARD_REFUEL_FRAMES = 360  # 2 s of fast-forward (3 frames per drawn frame)
# User's measurement: best star wind reachable with N jumps of fuel (extrapolated below 4, capped above 9).
BEST_WIND = {1: 1.667, 2: 1.846, 3: 2.026, 4: 2.206, 5: 2.416, 6: 2.604, 7: 2.776, 8: 2.962, 9: 3.104}
DAMAGE_WEIGHTS = {"normal": (0.6, 0.4), "capture": (0.75, 0.25), "destroy": (0.3, 0.7)}
# Comfortable range by agility (equivalent turn, degrees/s): (agility, range) anchors, interpolated.
COMFORT_RANGE = [(45, 900.0), (80, 600.0), (110, 400.0), (140, 0.0)]
GUN_FULL_AGILITY = 110.0


@dataclass
class Role:
    combat: bool = True
    # Fighters and drones follow the non-combat weapon rules.
    fighter: bool = False
    hero: bool = False                  # player-flown: no afterburner by default
    goal: str = "normal"                # normal | capture | destroy
    fight_seconds: float = 240.0        # 90 for escorts/guards, 240 for dedicated fighting ships
    evader: bool = False
    must_run_dark: bool = False
    long_range: bool = False            # ramscoop rule 2: never needs to refuel at planets
    needs_ramscoop: bool = True         # ramscoop rule 1
    needs_drives: bool = True           # hyperdrive, jump drive, quantum keystone
    needs_anti_missile: bool = True


@dataclass
class WeaponStats:
    name: str
    count: int
    turret: bool
    range: float
    dropoff: tuple[float, float] | None
    dropoff_modifier: float
    # Per frame, for all copies together.
    shield_damage: float
    hull_damage: float
    energy: float
    heat: float
    fuel: float
    hit_force: float
    anti_missile: float
    tractor: float

    @property
    def offensive(self) -> bool:
        return (self.shield_damage + self.hull_damage) > 0 and not self.anti_missile and not self.tractor


@dataclass
class Check:
    name: str
    passed: bool | None      # None: informational or not yet implemented
    detail: str


@dataclass
class Ship:
    hull: Hull
    outfits: dict[str, int]
    attributes: dict[str, float]
    mass: float
    cost: float
    fit_errors: list[str]
    weapons: list[WeaponStats]
    unknown_outfits: list[str] = field(default_factory=list)

    def get(self, key: str) -> float:
        return self.attributes.get(key, 0.0)

    # --- Movement (Ship.cpp, ShipInfoDisplay.cpp) ---
    @property
    def inertial_mass(self) -> float:
        return self.mass / (1 + self.get("inertia reduction"))

    @property
    def drag(self) -> float:
        drag = self.get("drag") / (1 + self.get("drag reduction"))
        return min(drag, self.inertial_mass)

    @property
    def max_speed(self) -> float:
        thrust = self.get("thrust") or self.get("afterburner thrust")
        return FPS * thrust / self.drag if self.drag else 0.0

    def _accel(self, thrust: float) -> float:
        return FPS * FPS * thrust * (1 + self.get("acceleration multiplier")) / self.inertial_mass

    @property
    def acceleration(self) -> float:
        return self._accel(self.get("thrust") or self.get("afterburner thrust"))

    @property
    def reverse_acceleration(self) -> float:
        return self._accel(self.get("reverse thrust"))

    @property
    def turn_rate(self) -> float:
        return FPS * self.get("turn") * (1 + self.get("turn multiplier")) / self.inertial_mass

    @property
    def agility(self) -> float:
        """Equivalent turn: √(turn × acceleration × 94 / 182), displayed units."""
        return math.sqrt(max(0.0, self.turn_rate * self.acceleration * 94 / 182))

    # --- Durability ---
    @property
    def max_shields(self) -> float:
        return self.get("shields") * (1 + self.get("shield multiplier"))

    @property
    def max_hull(self) -> float:
        return self.get("hull") * (1 + self.get("hull multiplier"))

    @property
    def shield_regen(self) -> float:
        return ((self.get("shield generation") + self.get("delayed shield generation"))
                * (1 + self.get("shield generation multiplier")))

    @property
    def hull_repair(self) -> float:
        return ((self.get("hull repair rate") + self.get("delayed hull repair rate"))
                * (1 + self.get("hull repair multiplier")))

    def _regen_cost(self, kind: str, resource: str) -> float:
        base = self.get(f"{kind} {resource}") + self.get(f"delayed {kind} {resource}")
        return base * (1 + self.get(f"{kind} {resource} multiplier"))

    @property
    def effective_shields(self) -> float:
        return self.max_shields * (1 + self.get("shield protection"))

    @property
    def effective_hull(self) -> float:
        return self.max_hull * (1 + self.get("hull protection"))

    # --- Heat (Ship.cpp, Entity.cpp, ShipAttributeCache.cpp) ---
    @property
    def max_heat(self) -> float:
        return 100 * (self.mass + self.get("heat capacity"))

    @property
    def cooling_efficiency(self) -> float:
        x = self.get("cooling inefficiency")
        return 2 + 2 / (1 + math.exp(-x / 2)) - 4 / (1 + math.exp(-x / 4)) if x else 1.0

    def equilibrium_heat(self, heat_in: float) -> float:
        """Steady heat level for a constant heat input per frame (Ship::IdleHeat, generalised)."""
        e = self.cooling_efficiency
        production = heat_in - e * self.get("cooling")
        if production <= 0:
            return 0.0
        dissipation = 0.001 * self.get("heat dissipation") + e * self.get("active cooling") / self.max_heat
        return production / dissipation if dissipation > 0 else math.inf

    # --- Energy and heat by activity, per frame ---
    @property
    def idle_energy(self) -> float:
        return self.get("energy generation") + self.get("fuel energy") - self.get("energy consumption")

    @property
    def idle_heat(self) -> float:
        return self.get("heat generation") + self.get("fuel heat")

    def activity(self, name: str) -> tuple[float, float]:
        """(energy used, heat produced) per frame while doing one thing at full rate."""
        if name == "thrust":
            return self.get("thrusting energy"), self.get("thrusting heat")
        if name == "reverse":
            return self.get("reverse thrusting energy"), self.get("reverse thrusting heat")
        if name == "turn":
            return self.get("turning energy"), self.get("turning heat")
        if name == "afterburner":
            return self.get("afterburner energy"), self.get("afterburner heat")
        if name == "regen":
            return (self._regen_cost("shield", "energy") + self._regen_cost("hull", "energy"),
                    self._regen_cost("shield", "heat") + self._regen_cost("hull", "heat"))
        if name == "cloak":
            return self.get("cloaking energy"), self.get("cloaking heat")
        if name == "weapons":
            return sum(w.energy for w in self.weapons), sum(w.heat for w in self.weapons)
        raise ValueError(name)

    # --- Fuel ---
    @property
    def average_jump_fuel(self) -> float:
        hyper = self.get("hyperdrive fuel") if self.get("hyperdrive") else 0.0
        jump = self.get("jump drive fuel") if self.get("jump drive") else 0.0
        if hyper and jump:
            return 0.75 * hyper + 0.25 * jump
        return hyper or jump

    @property
    def jumps(self) -> int:
        fuel = self.average_jump_fuel
        return int(self.get("fuel capacity") // fuel) if fuel else 0

    @property
    def has_torch(self) -> bool:
        return self.get("thrusting fuel") > 0 or self.get("thrusting energy") < 0

    # --- Weapons ---
    def weapon_value(self, weapon: WeaponStats, goal: str = "normal") -> float:
        """Weighted damage per frame after the range and fixed-gun penalties."""
        shield_w, hull_w = DAMAGE_WEIGHTS[goal]
        value = shield_w * weapon.shield_damage + hull_w * weapon.hull_damage
        comfort = comfortable_range(self.agility)
        if weapon.range < comfort:
            value *= (weapon.range / comfort) ** 2
        if not weapon.turret and self.agility < GUN_FULL_AGILITY:
            value *= (self.agility / GUN_FULL_AGILITY) ** 2
        return value


def comfortable_range(agility: float) -> float:
    points = COMFORT_RANGE
    if agility <= points[0][0]:
        return points[0][1]
    for (a0, r0), (a1, r1) in zip(points, points[1:]):
        if agility <= a1:
            return r0 + (r1 - r0) * (agility - a0) / (a1 - a0)
    return 0.0


def _fixed(value: float) -> float:
    return round(value * 10000) / 10000


def weapon_damage(game: GameData, weapon: Weapon, key: str, depth: int = 0) -> float:
    """Damage per shot including submunitions (Weapon::TotalDamage)."""
    total = weapon.stats.get(key, 0.0)
    if "exclude submunition damage" in weapon.flags or depth > 10:
        return total
    for name, count in weapon.submunitions:
        sub = game.outfits.get(name)
        if sub is not None and sub.weapon is not None:
            total += count * weapon_damage(game, sub.weapon, key, depth + 1)
    return total


def weapon_range(game: GameData, weapon: Weapon) -> float:
    """Weapon::Range: range override, else velocity × total lifetime (with submunitions)."""
    stats = weapon.stats
    if stats.get("range override", 0) > 0:
        return stats["range override"]

    def lifetime(w: Weapon, depth: int = 0) -> float:
        subs = [game.outfits[n].weapon for n, _ in w.submunitions
                if n in game.outfits and game.outfits[n].weapon is not None and depth < 10]
        return w.stats.get("lifetime", 0.0) + max((lifetime(s, depth + 1) for s in subs), default=0.0)

    velocity = stats.get("velocity override") or stats.get("velocity", 0.0)
    return velocity * lifetime(weapon)


def _weapon_stats(game: GameData, outfit: Outfit, count: int) -> WeaponStats:
    w = outfit.weapon
    rate = count / max(w.stats.get("reload", 1.0), 1.0)  # average shots per frame, bursts included
    return WeaponStats(
        name=outfit.name, count=count, turret=outfit.attributes.get("turret mounts", 0) < 0,
        range=weapon_range(game, w), dropoff=w.damage_dropoff,
        dropoff_modifier=w.stats.get("dropoff modifier", 0.0),
        shield_damage=max(0.0, weapon_damage(game, w, "shield damage")) * rate,
        hull_damage=max(0.0, weapon_damage(game, w, "hull damage")) * rate,
        energy=w.stats.get("firing energy", 0.0) * rate,
        heat=w.stats.get("firing heat", 0.0) * rate,
        fuel=w.stats.get("firing fuel", 0.0) * rate,
        hit_force=w.stats.get("hit force", 0.0) * rate,
        anti_missile=w.stats.get("anti-missile", 0.0),
        tractor=w.stats.get("tractor beam", 0.0),
    )


def build(game: GameData, hull: Hull, outfits: dict[str, int]) -> Ship:
    """Total up a hull and its outfits, and check the game's fit rule."""
    attrs = dict(hull.attributes)
    mass, cost = hull.mass, hull.cost
    weapons: list[WeaponStats] = []
    unknown: list[str] = []
    for name, count in outfits.items():
        outfit = game.outfits.get(name)
        if outfit is None:
            unknown.append(name)
            continue
        mass += outfit.mass * count
        cost += outfit.cost * count
        for key, value in outfit.attributes.items():
            attrs[key] = _fixed(attrs.get(key, 0.0) + value * count)
        if outfit.weapon is not None:
            weapons.append(_weapon_stats(game, outfit, count))

    # Fit rule (Outfit::CanAdd): every attribute an outfit touches stays at or above its minimum.
    errors = []
    touched = {k for name in outfits if name in game.outfits for k in game.outfits[name].attributes}
    automaton = attrs.get("automaton", 0) > 0
    for key in sorted(touched):
        minimum = MINIMUMS.get(key, 0.0)
        if key == "required crew":
            minimum = 0.0 if automaton else 1.0
        if minimum is not None and attrs.get(key, 0.0) < minimum - 1e-9:
            errors.append(f"{key}: {attrs.get(key, 0.0):g} (minimum {minimum:g})")
    if unknown:
        errors.append("unknown outfits: " + ", ".join(unknown))
    return Ship(hull, dict(outfits), attrs, mass, cost, errors, weapons, unknown)


def evaluate(ship: Ship, role: Role) -> list[Check]:
    """Check a ship against the design rules in docs/design-notes.md."""
    checks: list[Check] = []
    add = lambda name, passed, detail: checks.append(Check(name, passed, detail))
    s = FPS  # displayed values are per second

    add("Fits (game rule)", not ship.fit_errors, "; ".join(ship.fit_errors) or "all capacities within limits")
    add("Can move", ship.get("thrust") > 0 and ship.get("turn") > 0,
        f"thrust {ship.get('thrust'):g}, turn {ship.get('turn'):g}")
    if role.needs_drives:
        missing = [d for d in ("hyperdrive", "jump drive", "quantum keystone") if not ship.get(d)]
        add("Drives", not missing, "missing: " + ", ".join(missing) if missing else "hyperdrive, jump drive, keystone")

    # Energy and heat in each job scenario, at the 90% heat target.
    solar = 0.0 if role.must_run_dark else ship.get("solar collection")
    solar_heat = ship.get("solar heat")
    weapon_share = 1.0 if role.combat and not role.fighter else WEAPON_SHARE_NON_COMBAT
    w_energy, w_heat = ship.activity("weapons")
    moves = {m: ship.activity(m) for m in ("regen", "thrust", "turn")}
    if ship.has_torch:
        rest = max(moves["regen"][0], moves["turn"][0]), max(moves["regen"][1], moves["turn"][1])
        move_energy = TORCH_THRUST_SHARE * moves["thrust"][0] + (1 - TORCH_THRUST_SHARE) * rest[0]
        move_heat = TORCH_THRUST_SHARE * moves["thrust"][1] + (1 - TORCH_THRUST_SHARE) * rest[1]
    else:
        move_energy = max(v[0] for v in moves.values())
        move_heat = max(v[1] for v in moves.values())
    scenarios = [("Weapons in combat", SOLAR_COMBAT,
                  weapon_share * w_energy + move_energy, weapon_share * w_heat + move_heat)]
    if role.evader:
        cloak = ship.activity("cloak")
        scenarios.append(("Evading (rule 3)", SOLAR_EVADING, cloak[0], cloak[1]))
    thrust = moves["thrust"]
    scenarios.append(("Near a bright star (rule 2b)", SOLAR_STAY, thrust[0], thrust[1]))

    steady_heat_fraction = 0.0
    for name, factor, load_energy, load_heat in scenarios:
        heat_in = ship.idle_heat + load_heat + solar_heat * factor
        heat = ship.equilibrium_heat(heat_in)
        fraction = heat / ship.max_heat if ship.max_heat else math.inf
        cooling_draw = ship.get("cooling energy") * min(1.0, fraction)
        net = ship.idle_energy + solar * factor - load_energy - cooling_draw
        if name == "Weapons in combat":
            steady_heat_fraction = fraction
        add(f"{name}: heat", fraction <= HEAT_TARGET, f"settles at {fraction:.0%} of max heat")
        add(f"{name}: energy", net >= 0, f"net {net * s:+.0f}/s (solar ×{factor:.2f})")

    if not (role.combat and not role.fighter):
        extra_energy = (1 - weapon_share) * w_energy * BURST_FRAMES
        extra_heat = (1 - weapon_share) * w_heat * BURST_FRAMES
        headroom = (HEAT_TARGET - steady_heat_fraction) * ship.max_heat
        add("Burst: all weapons 2.5 s", extra_energy <= ship.get("energy capacity") and extra_heat <= headroom,
            f"needs {extra_energy:.0f} energy (have {ship.get('energy capacity'):.0f}), "
            f"{extra_heat:.0f} heat (headroom {headroom:.0f})")

    # Heat-gated movement: negative heat costs need that much heat present.
    idle_level = ship.equilibrium_heat(ship.idle_heat)
    for mode in ("thrust", "reverse", "turn"):
        cost = ship.activity(mode)[1]
        if cost < 0:
            add(f"Heat-gated {mode}", idle_level >= -cost,
                f"idle heat {idle_level:.0f} vs {-cost:.1f} needed per frame")

    # Fuel and ramscoop.
    ramscoop = ship.get("ramscoop")
    if role.needs_ramscoop:
        add("Ramscoop (rule 1)", ramscoop > 0, f"ramscoop {ramscoop:g}")
    jumps = ship.jumps
    if role.long_range and ship.average_jump_fuel:
        wind = BEST_WIND[min(max(jumps, 1), 9)]
        per_frame = 0.03 * wind * 2.0 * math.sqrt(ramscoop) + ship.get("fuel generation")
        seconds = ship.average_jump_fuel / per_frame / 180 if per_frame else math.inf
        add("Refuel one jump (rule 2)", seconds <= 2.0,
            f"{seconds:.1f} s of fast-forward with {jumps} jumps of fuel (best wind {wind})")
    fight_fuel = 0.0
    frames = role.fight_seconds * FPS
    if role.combat and ship.has_torch:
        fight_fuel += TORCH_THRUST_SHARE * ship.get("thrusting fuel") * frames
    if role.combat and not role.hero and ship.get("afterburner thrust"):
        fight_fuel += 0.10 * ship.get("afterburner fuel") * frames
    if fight_fuel:
        recovery = (0.03 * WIND_COMBAT * math.sqrt(ramscoop) + ship.get("fuel generation")) * frames
        need = ship.average_jump_fuel + fight_fuel - recovery
        add("Fuel for a fight", ship.get("fuel capacity") >= need,
            f"needs {need:.0f} (jump reserve + {fight_fuel:.0f} burned − {recovery:.0f} recovered), "
            f"has {ship.get('fuel capacity'):.0f}")

    if role.needs_anti_missile and not role.fighter:
        has_am = any(w.anti_missile for w in ship.weapons)
        add("Anti-missile", has_am, "has anti-missile" if has_am else "no anti-missile turret")
    if role.hero and ship.get("afterburner thrust"):
        add("No afterburner on the hero ship", False, "afterburner fitted")

    # Informational.
    t, r, u, d = ship.get("thrust"), ship.get("reverse thrust"), ship.get("turn"), ship.get("drag")
    if t and u:
        useless = t * u / (u + 180 * d) if d else 0.0
        balanced, nimble = u / 60, (u / 60 + t) / 2
        level = ("none" if not r else "useless" if r < useless else "useful" if r < balanced
                 else "balanced" if r < nimble else "nimble")
        add("Reverse thrust", None, f"{r:g}: {level} (useful > {useless:.1f}, balanced {balanced:.1f}, "
            f"nimble {nimble:.1f})")
    add("Agility", None, f"{ship.agility:.0f} (comfortable weapon range ≥ {comfortable_range(ship.agility):.0f})")
    add("Not yet checked", None, "outlier scenarios (dark transit, passing a 90th-percentile star) "
        "need the jump rules and a frame simulation")
    return checks
