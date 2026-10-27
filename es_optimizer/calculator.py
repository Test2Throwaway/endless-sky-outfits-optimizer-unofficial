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
# Solar cases a request can pick (N9): factor for cruising, recovering and fighting. "bright" and "hug" also raise
# the near-a-bright-star check to at least that factor.
LIGHT = {"dark": 0.0, "dim": SOLAR_EVADING, "median": SOLAR_COMBAT, "bright": SOLAR_STAY, "hug": 7.7}
# War zones for the exposure window (N27): governments whose ships fire on a third party there.
WAR_ZONES = {"wah ki": ("Hai", "Hai (Unfettered)"), "mesuket": ("Kor Mereti", "Kor Sestor")}
# Exposure window: incoming fire = the strongest ship plus 2 of the strongest among the fastest share of ships.
EXPOSURE_FAST_SHARE = 0.2
EXPOSURE_FAST_COUNT = 2
WIND_COMBAT = 0.75 * 0.65       # 30th-percentile wind at 3000
# While refuelling the pilot keeps the ship between about 5 and 100 from the star (flybys, orbiting):
# use the distance factor averaged over that range.
REFUEL_SCALE = (0.2 * 95 + 1800 * math.log(1.1 / 1.005)) / 95
HEAT_TARGET = 0.9               # design target: at or below 90% of max heat
BURST_FRAMES = 150              # 2.5 s of all weapons for non-combat ships
WEAPON_SHARE_NON_COMBAT = 0.5
TORCH_THRUST_SHARE = 0.85
# Duty cycles (user): out of combat, and in combat on top of the weapons, a ship thrusts 70% and turns 30% of the time.
CRUISE_THRUST = 0.7
CRUISE_TURN = 0.3
# Recovery after a fight: the greater of shield regen for 1.4× the time to refill shields with hull repair for 1× the
# time to repair from the disabled threshold, or 1× and 1.4×.
RECOVERY_LONG = 1.4
# Combat by game stage (user; observed in tools/warzone.py, aside/warzone-observation.md): the designed fight is the
# 80th percentile of warship fleet-fight length in that stage's war zone, and weapons fire at the median observed
# duty: guns, turrets, and secondaries (outfit category "Secondary Weapons"), across the whole fight. Beginner =
# human space vs pirates, early mid = Hai (Wah Ki), late mid = Kor (Mesuket). The tool designs for late mid game
# unless a role or request says otherwise (user).
@dataclass(frozen=True)
class Stage:
    fight_seconds: float
    gun_share: float
    turret_share: float
    secondary_share: float


STAGES = {
    "beginner": Stage(44.0, 0.28, 0.28, 0.76),
    "early-mid": Stage(86.0, 0.37, 0.37, 0.90),
    "late-mid": Stage(102.0, 0.70, 0.65, 0.79),
}
DEFAULT_STAGE = "late-mid"
# Calibration overrides: a number replaces the stage's gun and turret duty (PRIMARY_SHARE) or secondary duty
# (SECONDARY_SHARE); None uses the stage.
PRIMARY_SHARE = None
SECONDARY_SHARE = None
# Combat without batteries (user): with batteries empty the ship must still work, degraded. Generation alone carries
# movement, cooling and shield regen plus this share of the stage's weapon fire, and at least the cheapest
# BATTERYLESS_WEAPONS weapons (installed copies; more if the ship has more than BATTERYLESS_MANY weapons).
BATTERYLESS_SHARE = 0.3
BATTERYLESS_WEAPONS = 1
BATTERYLESS_MANY = 6


def batteryless_minimum(weapons: list, role: "Role", buffer: float = math.inf) -> float:
    """Energy per frame for the cheapest 1 (or 2, with more than BATTERYLESS_MANY) damage-weapon copies at their
    stage duty. Instantaneous draw: with batteries drained, spare generation refills the storage and a weapon fires
    whenever one shot's energy has built up, so it only counts if one shot fits in `buffer` (energy capacity plus a
    frame of generation, as in Ship::FlightCheck). If too few fit, the minimum is infinite."""
    copies = [w for w in weapons if w.offensive and w.count for _ in range(w.count)]
    if not copies:
        return 0.0
    need = BATTERYLESS_WEAPONS + (1 if len(copies) > BATTERYLESS_MANY else 0)
    per_copy = sorted(weapon_duty(role, w) * w.energy / w.count for w in copies if w.shot_energy <= buffer)
    return sum(per_copy[:need]) if len(per_copy) >= need else math.inf

# Shield regeneration alone carries a fight if shields refill within this share of the designed fight length;
# otherwise hull repair runs during the fight too. To be tuned (user: "ratio to be determined").
SHIELD_SELF_SUFFICIENT = 1.0
# Interceptors don't need a combat energy and heat balance; their reserves must carry a 90 s battle at 50% weapons.
INTERCEPTOR_BATTLE_FRAMES = 90 * 60
CARRIED_CATEGORIES = ("Fighter", "Drone")
# Combat roles: a weapon firing fewer than this many shots per second (per copy) loses damage value, more the
# slower it fires: value × (shots per second / COMBAT_MIN_SHOTS) ^ COMBAT_RATE_EXPONENT. Damage only (shield and
# hull); utility (anti-missile, tractor, push and pull, disruption) is not affected.
COMBAT_MIN_SHOTS = 6.0
COMBAT_RATE_EXPONENT = 1.07          # keeps ~20% at 1.33 shots per second (user, from play)
# Slow turrets lose damage value: × (turret turn in degrees per second / TURRET_TURN_FULL) ^ TURRET_TURN_EXPONENT,
# up to 1. Full value at the median turret (about 150°/s). Homing weapons are exempt (the projectile steers).
TURRET_TURN_FULL = 150.0
TURRET_TURN_EXPONENT = 1.0
# Slow projectiles lose damage value: × (projectile speed in pixels per second / PROJECTILE_SPEED_FULL) ^ exponent,
# up to 1: the target has longer to react, and more shots are in flight to a target that dies before they land.
# Speed, not flight time, so long range isn't penalized. Full value from the median weapon (about 600 px/s) up.
# Instantaneous weapons (beams, hitting in the frame they fire) count as infinitely fast: always full value.
PROJECTILE_SPEED_FULL = 600.0
PROJECTILE_SPEED_EXPONENT = 1.0
# Energy made by thrusting (e.g. the Inductive Extractor) counts only as much as the ship can afford to keep
# thrusting: the torch share times min(1, agility / GUN_FULL_AGILITY). A slow tank can't count on it.
# Magazine (ammo) weapons with long range are used in the opening part of a fight: the first 50% of an escort
# fight and 35% of a dedicated fight. That sets both their magazine depth and their share of damage.
LONG_RANGE = 1100.0
# Observed: secondaries fire throughout a fight, not just the opening, so no window by default ({} = the whole fight).
MAGAZINE_WINDOW = {}
FAST_FORWARD_REFUEL_FRAMES = 360  # 2 s of fast-forward (3 frames per drawn frame)
# User's measurement: best star wind reachable with N jumps of fuel (extrapolated below 4, capped above 9).
# Survivability (user): damage the ship can absorb, sustained (regeneration) and in a burst (shields plus hull above
# the disable line). Shield regeneration is worth more than hull repair: damage hits shields first, low hull disables
# the ship and stops all repair, shields block more damage types, and shield generators give several times more
# regeneration per outfit space. How much hull repair counts follows the hull's own shield-to-hull balance: weight =
# bare hull / (bare shields + hull), at least HULL_REPAIR_FLOOR (a typical warship hull ≈ 0.36, so hull repair still
# wins if it is about 3× as space-efficient as the shield option).
HULL_REPAIR_FLOOR = 0.25
# Turn rate to acceleration (user: a STRONG push on every design to stay in the stock range). Mass cancels, so this
# is the engine mix: turn / (60 × thrust). The band is the 10th–90th percentile over the 653 stock ships (0.11.2; every
# class falls within about 0.25–0.83). Outside it the score drops by TURN_ACCEL_PENALTY per doubling.
TURN_ACCEL_BAND = (0.29, 0.77)
TURN_ACCEL_PENALTY = 0.5


def turn_accel_ratio(ship: "Ship") -> float | None:
    return ship.turn_rate / ship.acceleration if ship.acceleration > 0 and ship.turn_rate > 0 else None


def turn_accel_penalty(ship: "Ship") -> float:
    """Score penalty: TURN_ACCEL_PENALTY per doubling outside TURN_ACCEL_BAND (0 inside, or for ships that can't move)."""
    ratio = turn_accel_ratio(ship)
    if ratio is None:
        return 0.0
    low, high = TURN_ACCEL_BAND
    if ratio < low:
        return TURN_ACCEL_PENALTY * math.log2(low / ratio)
    if ratio > high:
        return TURN_ACCEL_PENALTY * math.log2(ratio / high)
    return 0.0


# A trip (user): from a safe staging system one jump away, jump in, fight, jump back out, and recover to full at the
# staging system before the next fight. Ships aren't refitted per target, so the staging star is a typical one: the
# 30th percentile, across the 0.11.2 map, of the strongest star wind within one jump (user's choice of percentile).
STAGING_WIND = 1.34
# How long the player waits at staging to recover, in game seconds, by mission (user: low patience for a routine
# fight, high for a prepared operation). Placeholders until the user sets them.
PATIENCE = {"routine": 180.0, "operation": 900.0}
# Fuel-burning thrusters on AI-flown ships: the AI has no fuel reserve for them (it keeps one jump only from the
# afterburner, AI::ShouldUseAfterburner), so they must be paid for by fuel income while escorting (user: option a).
# False forbids them on AI-flown combat ships outright (option c).
TORCH_ESCORTS = True
BEST_WIND = {1: 1.667, 2: 1.846, 3: 2.026, 4: 2.206, 5: 2.416, 6: 2.604, 7: 2.776, 8: 2.962, 9: 3.104}
# Shield / hull damage weights by goal. "capture-intact" uses the destroy weights on instantaneous weapons
# when shield disruption is available, and the disable weights otherwise.
DAMAGE_WEIGHTS = {"normal": (0.6, 0.4), "disable": (0.75, 0.25), "destroy": (0.3, 0.7)}
GOALS = ["normal", "disable", "capture-intact", "destroy"]
# Capture-intact: the target must be disabled while still at or above half its shields. 80% of the damage
# on it comes from capture-intact ships (assumed: this ship alone, the worst case for disruption) and 20% from
# stock ships, whose damage is 53% shield / 47% hull on average across stock loadouts.
CAPTURE_SHIELDS_LEFT = 0.5
CAPTURE_OWN_SHARE = 0.8
STOCK_SHIELD_SHARE = 0.53
CAPTURE_FACTIONS = ("pug", "korath", "heliarch", "kahet", "quarg")
# Comfortable range by agility (equivalent turn, degrees/s): (agility, range) anchors, interpolated.
COMFORT_RANGE = [(45, 900.0), (80, 600.0), (110, 400.0), (140, 0.0)]
GUN_FULL_AGILITY = 110.0


@dataclass
class Role:
    combat: bool = True
    # Fighters and drones follow the non-combat weapon rules.
    fighter: bool = False
    hero: bool = False                  # player-flown: no afterburner by default
    # normal | disable (general disabling, looting, capturing) | capture-intact (a specific hull must
    # survive being disabled) | destroy
    goal: str = "normal"
    stage: str = DEFAULT_STAGE          # game stage: fight length and weapon duty (STAGES)
    fight_seconds: float = STAGES[DEFAULT_STAGE].fight_seconds
    evader: bool = False
    fights_per_restock: int = 2         # magazine depth: fights between visits to an outfitter
    must_run_dark: bool = False
    long_range: bool = False            # ramscoop rule 2: never needs to refuel at planets
    needs_ramscoop: bool = True         # ramscoop rule 1
    needs_drives: bool = True           # hyperdrive, jump drive, quantum keystone
    excluded_drives: frozenset = frozenset()   # drives a role says the ship must not have
    needs_anti_missile: bool = True
    needs_regen: bool = True            # some shield generation or hull repair
    # Every damage weapon the player can get (set by the solver and the CLI). Weapon value is relative to the average
    # of these at the ship's agility: the discounts rank weapons against each other, not weapons against the rest of
    # the ship. Empty: no normalization.
    reference_weapons: tuple = ()
    # Hull name -> agility with its stock outfits: the average is taken there, a fixed point per hull, so a design
    # can't raise its weapon value by making itself slower.
    stock_agility: dict = field(default_factory=dict)
    # Experiment: homing weapons skip the fire-rate, fixed-gun and projectile-speed discounts; the fixed-gun and
    # short-range discounts are straight lines instead of squared.
    weapon_tweaks: bool = False
    # Levers (see docs/roles.md).
    # A chain of fights with recovery gaps between them: ((fight seconds, gap seconds), ...); empty = one fight of
    # fight_seconds.
    fight_chain: tuple = ()
    start_state: str = "cruise"         # combat starts at cruising heat, or "hot" (bright-star equilibrium)
    light: str = ""                     # solar case (LIGHT); "" = the default factors
    cloak_duty: float = 0.0             # share of the time cloaked (cloaking costs in the cruising load)
    patience: str = "routine"           # recovery time allowed at staging between fights (PATIENCE)
    war_zone: str = ""                  # incoming fire for the exposure window (WAR_ZONES)
    exposure_seconds: float = 0.0       # must survive this long uncloaked under the war zone's fire
    exposure_dps: float = 0.0           # incoming damage per second (set by the solver from the war zone)
    denial_targets: tuple = ()          # ((inertial mass, braking per frame, jump speed), ...) set by the solver


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
    disruption: float = 0.0
    piercing: float = 0.0
    # Ammunition outfit used, and amount per frame of continuous fire (all copies together).
    ammo: str | None = None
    ammo_rate: float = 0.0
    # Hits in the frame it is fired (lifetime of one frame, no submunitions): stops dealing damage at once.
    instantaneous: bool = False
    shot_energy: float = 0.0            # firing energy of one shot
    shots_per_second: float = 0.0       # one copy, bursts averaged in
    secondary: bool = False             # outfit category "Secondary Weapons"
    turret_turn: float = 0.0            # degrees per second
    projectile_speed: float = 0.0       # pixels per second (top speed for accelerating projectiles)
    homing: bool = False
    # Effect damage per frame, all copies (EFFECT_DAMAGE keys without " damage"), e.g. {"ion": 0.4}.
    effects: dict = field(default_factory=dict)
    blast_radius: float = 0.0
    shot_damage: float = 0.0            # shield + hull damage of one shot
    shot_force: float = 0.0             # hit force of one shot (negative: pull)
    capacity: float = 0.0               # weapon capacity used, all copies

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
    # Each fitted outfit's own attributes (for metrics that rank outfits, e.g. boarding strength).
    outfit_attributes: dict = field(default_factory=dict)

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
    def minimum_hull(self) -> float:
        """Ship::MinimumHull: the hull level at which the ship is disabled."""
        if self.hull.never_disabled:
            return 0.0
        absolute = self.get("absolute threshold")
        if absolute > 0:
            return absolute
        percent = self.get("threshold percentage")
        transition = 1 / (1 + 0.0005 * self.max_hull)
        fraction = min(percent, 1.0) if percent > 0 else 0.1 * (1 - transition) + 0.5 * transition
        return max(0.0, math.floor(self.max_hull * fraction + self.get("hull threshold")))

    @property
    def hull_shield_share(self) -> float:
        """The bare hull's shields / (shields + hull): how much the hull is built around its shields."""
        shields, hull = self.hull.attributes.get("shields", 0.0), self.hull.attributes.get("hull", 0.0)
        return shields / (shields + hull) if shields + hull > 0 else 0.0

    @property
    def sustained_absorb(self) -> float:
        """Damage per second absorbed indefinitely: shield regeneration, plus hull repair weighted by the hull's
        balance (1 − shield share, at least HULL_REPAIR_FLOOR)."""
        weight = max(HULL_REPAIR_FLOOR, 1 - self.hull_shield_share)
        return FPS * (self.shield_regen * (1 + self.get("shield protection"))
                      + weight * self.hull_repair * (1 + self.get("hull protection")))

    @property
    def burst_absorb(self) -> float:
        """Damage absorbed before the ship is disabled: shields plus hull above the disable line."""
        return (self.max_shields * (1 + self.get("shield protection"))
                + max(0.0, self.max_hull - self.minimum_hull) * (1 + self.get("hull protection")))

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
    def disable_threshold(self) -> float:
        """Hull level below which the ship is disabled (Ship::FinishLoading)."""
        absolute = self.get("absolute threshold")
        if absolute > 0:
            return absolute
        hull = self.max_hull
        percent = self.get("threshold percentage")
        transition = 1 / (1 + 0.0005 * hull)
        fraction = min(percent, 1.0) if percent > 0 else 0.1 * (1 - transition) + 0.5 * transition
        return max(0.0, math.floor(hull * fraction + self.get("hull threshold")))

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

    def heat_after(self, heat_in: float, frames: float, start: float = 0.0) -> float:
        """Heat level after some frames of constant heat input, starting from `start` (below the overheat limit
        dissipation and active cooling are proportional to heat, so heat approaches its equilibrium exponentially)."""
        e = self.cooling_efficiency
        k = 0.001 * self.get("heat dissipation") + e * self.get("active cooling") / self.max_heat
        production = heat_in - e * self.get("cooling")
        if k <= 0:
            return max(0.0, start + production * frames)
        target = production / k
        return max(0.0, target + (start - target) * (1 - k) ** frames)

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
    def weapon_value(self, weapon: WeaponStats, goal: str = "normal", disruption_available: bool = False,
                     fight_seconds: float = 240.0, combat: bool = False, reference: tuple = (),
                     reference_agility: float | None = None, tweaks: bool = False) -> float:
        """Weighted damage per frame × how well the weapon suits this ship (range, fixed gun, magazine window, fire
        rate in combat roles, turret turn, projectile speed), relative to the average of the `reference` weapons on
        a ship of `reference_agility` (default: this ship's): an average weapon counts its full damage."""
        if goal == "capture-intact":
            if not weapon.instantaneous:
                return 0.0
            shield_w, hull_w = DAMAGE_WEIGHTS["destroy" if disruption_available else "disable"]
        else:
            shield_w, hull_w = DAMAGE_WEIGHTS[goal]
        value = shield_w * weapon.shield_damage + hull_w * weapon.hull_damage
        factor = suitability(weapon, self.agility, fight_seconds, combat, tweaks)
        if reference:
            at = self.agility if reference_agility is None else reference_agility
            factor /= average_suitability(reference, round(at, 1), fight_seconds, combat, goal, tweaks)
        return value * factor


def suitability(weapon: WeaponStats, agility: float, fight_seconds: float = 240.0, combat: bool = False,
                tweaks: bool = False) -> float:
    """How much of a weapon's damage counts on a ship this agile: short range against the comfortable range
    (squared), fixed guns on ships below GUN_FULL_AGILITY (squared), fire rate (combat roles), turret turn,
    projectile speed and the magazine window, multiplied."""
    factor = 1.0
    power = 1 if tweaks else 2
    homing = tweaks and weapon.homing
    comfort = comfortable_range(agility)
    if weapon.range < comfort:
        factor *= (weapon.range / comfort) ** power
    if not weapon.turret and agility < GUN_FULL_AGILITY and not homing:
        factor *= (agility / GUN_FULL_AGILITY) ** power
    factor *= dropoff_factor(weapon, min(weapon.range, comfort) if comfort > 0 else weapon.range)
    if combat and not homing:
        factor *= fire_rate_factor(weapon)
    factor *= turret_turn_factor(weapon) * (1.0 if homing else projectile_speed_factor(weapon))
    return factor * magazine_window(weapon, fight_seconds)


# The average is never taken as less than this, so a ship no weapon suits doesn't get huge multipliers.
MIN_AVERAGE_SUITABILITY = 0.05
_average_cache: dict = {}


def average_suitability(reference: tuple, agility: float, fight_seconds: float, combat: bool, goal: str,
                        tweaks: bool = False) -> float:
    """Mean suitability of the reference weapons on a ship this agile (capture-intact: non-instantaneous count 0)."""
    key = (id(reference), len(reference), agility, fight_seconds, combat, goal, tweaks)
    if key not in _average_cache:
        values = [0.0 if goal == "capture-intact" and not w.instantaneous else
                  suitability(w, agility, fight_seconds, combat, tweaks) for w in reference]
        _average_cache[key] = max(MIN_AVERAGE_SUITABILITY, sum(values) / len(values)) if values else 1.0
    return _average_cache[key]


def dropoff_factor(weapon: WeaponStats, distance: float) -> float:
    """Average share of full damage over engagements from point blank out to `distance` (Weapon::DamageDropoff:
    full damage up to the dropoff start, falling linearly to the dropoff modifier at its end)."""
    dropoff = getattr(weapon, "dropoff", None)
    if not dropoff or distance <= 0:
        return 1.0
    start, end = dropoff
    low = weapon.dropoff_modifier
    end = max(end, start)

    def at(d: float) -> float:
        if d <= start:
            return 1.0
        if d >= end:
            return low
        return 1.0 + (low - 1.0) * (d - start) / (end - start)

    # Piecewise linear: integrate exactly over [0, distance].
    points = sorted({0.0, distance, *(x for x in (start, end) if 0 < x < distance)})
    area = sum((b - a) * (at(a) + at(b)) / 2 for a, b in zip(points, points[1:]))
    return area / distance


def fire_rate_factor(weapon: WeaponStats) -> float:
    """Combat roles: damage value kept by a weapon firing fewer than COMBAT_MIN_SHOTS shots per second."""
    return min(1.0, weapon.shots_per_second / COMBAT_MIN_SHOTS) ** COMBAT_RATE_EXPONENT


def turret_turn_factor(weapon: WeaponStats) -> float:
    """Damage value kept by a slow-turning turret (guns and homing weapons: 1)."""
    if not weapon.turret or weapon.homing:
        return 1.0
    return min(1.0, weapon.turret_turn / TURRET_TURN_FULL) ** TURRET_TURN_EXPONENT


def projectile_speed_factor(weapon: WeaponStats) -> float:
    """Damage value kept by a weapon with slow projectiles. Instantaneous weapons are the fastest there is: 1."""
    if weapon.instantaneous:
        return 1.0
    return min(1.0, weapon.projectile_speed / PROJECTILE_SPEED_FULL) ** PROJECTILE_SPEED_EXPONENT


def cruise_load(ship: "Ship") -> tuple[float, float]:
    """(energy, heat) per frame of moving about: thrust CRUISE_THRUST and turn CRUISE_TURN of the time. Energy made
    by thrusting counts only as much as the ship is nimble enough to keep thrusting (see thrust_shares)."""
    thrust_e, thrust_h = ship.activity("thrust")
    turn_e, turn_h = ship.activity("turn")
    thrust_share = CRUISE_THRUST * (min(1.0, ship.agility / GUN_FULL_AGILITY) if thrust_e < 0 else 1.0)
    return thrust_share * thrust_e + CRUISE_TURN * turn_e, CRUISE_THRUST * thrust_h + CRUISE_TURN * turn_h


def regen_times(ship: "Ship") -> tuple[float | None, float | None]:
    """Frames to refill shields from empty, and to repair hull from the disabled threshold to full (None: no regen)."""
    shields = ship.max_shields / ship.shield_regen if ship.shield_regen > 0 and ship.max_shields > 0 else None
    damage = ship.max_hull - ship.disable_threshold
    hull = damage / ship.hull_repair if ship.hull_repair > 0 and damage > 0 else None
    # Regeneration starts once the delay after the last hit runs out (shields from empty use the depleted delay).
    if shields is not None:
        shields += max(ship.get("shield delay"), ship.get("depleted shield delay"))
    if hull is not None:
        hull += max(ship.get("repair delay"), ship.get("disabled repair delay"))
    return shields, hull


def run_phases(ship: "Ship", phases: list[tuple[float, float, float]], start_heat: float) -> tuple[float, float]:
    """Step through phases of (frames, net energy per frame, heat input per frame), starting with full batteries
    and `start_heat`: (lowest stored energy, highest heat). Within a phase heat moves monotonically towards its
    equilibrium, so its highest value is at a phase boundary; batteries never fill beyond capacity."""
    capacity = ship.get("energy capacity")
    energy, heat = capacity, start_heat
    low, peak = capacity, start_heat
    for frames, net, heat_in in phases:
        if frames <= 0:
            continue
        heat = ship.heat_after(heat_in, frames, heat)
        peak = max(peak, heat)
        energy = min(capacity, energy + net * frames)
        low = min(low, energy)
    return low, peak


def thrust_shares(ship: "Ship") -> tuple[float, float]:
    """Share of time spent thrusting for a torch ship: for costs, and for energy made by thrusting (smaller for
    ships that aren't nimble enough to keep thrusting in a fight)."""
    return TORCH_THRUST_SHARE, TORCH_THRUST_SHARE * min(1.0, ship.agility / GUN_FULL_AGILITY)


def magazine_window(weapon: WeaponStats, fight_seconds: float) -> float:
    """Share of a fight a weapon is used for: long-range magazine weapons only open the fight."""
    if weapon.ammo and weapon.range > LONG_RANGE:
        return magazine_share(fight_seconds)
    return 1.0


# Anti-missile (Hardpoint::FireAntiMissile): a shot kills when Random::Int(strength) > Random::Int(missile strength).
# Value = missile kills per second against a typical missile (MISSILE_STRENGTH, the median in the game data) ×
# (range / AM_REFERENCE_RANGE) ^ exponent. A ship defending itself gets more shots at a missile the farther it
# reaches (exponent 1); a point-defence ship covers an area around itself that grows with range squared
# (exponent 2, user: PD ships prioritise range more than ships defending themselves).
MISSILE_STRENGTH = 24.0
AM_REFERENCE_RANGE = 300.0
AM_SELF_RANGE_EXPONENT = 1.0
AM_FLEET_RANGE_EXPONENT = 2.0


def missile_kill_chance(strength: float, missile: float = None) -> float:
    """P(Random::Int(strength) > Random::Int(missile)): Random::Int(n) is uniform over 0 … n−1."""
    s, m = int(strength), int(MISSILE_STRENGTH if missile is None else missile)
    if s <= 0:
        return 0.0
    if m <= 0:
        return (s - 1) / s
    return sum(min(x, m) for x in range(s)) / (s * m)


def anti_missile_value(weapons: list, exponent: float) -> float:
    """Missile kills per second, weighted by (range / AM_REFERENCE_RANGE) ^ exponent, summed over turrets."""
    return sum(w.count * w.shots_per_second * missile_kill_chance(w.anti_missile)
               * (w.range / AM_REFERENCE_RANGE) ** exponent for w in weapons if w.anti_missile)


ALPHA_SECONDS = 10.0       # alpha damage: damage per second over the opening seconds, on batteries
DENIAL_HOLD = 0.5          # denial range: farthest range at which jump denial is at least this share


def alpha_dps(ship: "Ship", role: "Role") -> float:
    """Shield + hull damage per second over the first ALPHA_SECONDS, limited by the energy on hand (batteries plus
    generation): bursty designs with batteries score here even if they can't sustain the fire."""
    frames = ALPHA_SECONDS * FPS
    weapons = [w for w in ship.weapons if w.offensive]
    need = sum(w.energy for w in weapons) * frames
    have = ship.get("energy capacity") + max(0.0, ship.idle_energy + ship.get("solar collection") * solar_factor(role)
                                              - cruise_load(ship)[0]) * frames
    share = min(1.0, have / need) if need > 0 else 1.0
    return FPS * share * sum(w.shield_damage + w.hull_damage for w in weapons)


def anti_fighter_value(ship: "Ship") -> float:
    """Damage per second against small fast targets: fire rate, projectile speed and turret turn all count fully."""
    total = 0.0
    for w in ship.weapons:
        if not w.offensive:
            continue
        rate = min(1.0, w.shots_per_second / COMBAT_MIN_SHOTS)
        total += (w.shield_damage + w.hull_damage) * rate * projectile_speed_factor(w) * turret_turn_factor(w)
    return FPS * total


def weapon_range_mean(ship: "Ship") -> float:
    weapons = [w for w in ship.weapons if w.offensive]
    damage = sum(w.shield_damage + w.hull_damage for w in weapons)
    return sum(w.range * (w.shield_damage + w.hull_damage) for w in weapons) / damage if damage else 0.0


def jump_denial(ship: "Ship", role: "Role", min_range: float = 0.0) -> float:
    """Share of the time a typical target is kept from jumping out (N29), averaged over the target classes: each hit
    with hit force adds |force| ÷ mass to its speed, and it must brake below its drive's jump speed before it can
    jump. Uses weapons reaching at least `min_range`."""
    if not role.denial_targets:
        return 0.0
    shares = []
    for mass, braking, jump_speed in role.denial_targets:
        held = 0.0
        for w in ship.weapons:
            if not w.shot_force or w.range < min_range:
                continue
            kick = abs(w.shot_force) / mass
            if kick > jump_speed and braking > 0:
                hits_per_frame = w.count * w.shots_per_second / FPS
                held += hits_per_frame * (kick - jump_speed) / braking
        shares.append(min(1.0, held))
    return sum(shares) / len(shares)


def denial_range(ship: "Ship", role: "Role") -> float:
    """Farthest range at which jump denial still holds at DENIAL_HOLD (N30); 0 if it never does."""
    best = 0.0
    for r in sorted({w.range for w in ship.weapons if w.shot_force}):
        if jump_denial(ship, role, r) >= DENIAL_HOLD:
            best = r
    return best


def exposure_margin(ship: "Ship", role: "Role") -> float:
    """Health that can be lost before being disabled, over the damage taken in the exposure window (≥ 1: survives).
    Shields and hull count with their protection; damage is taken as half shield, half hull damage."""
    health = ship.effective_shields + max(0.0, ship.max_hull - ship.disable_threshold) * (1 + ship.get("hull protection"))
    incoming = role.exposure_dps * role.exposure_seconds
    return health / incoming if incoming > 0 else math.inf


def solar_factor(role: "Role") -> float:
    """Solar factor while cruising, recovering and fighting."""
    if role.must_run_dark:
        return 0.0
    return LIGHT.get(role.light, SOLAR_COMBAT)


def stay_factor(role: "Role") -> float:
    """Solar factor for the near-a-bright-star check."""
    return max(SOLAR_STAY, LIGHT.get(role.light, 0.0))


def combat_plan(role: "Role") -> list[tuple[float, bool, bool]]:
    """The designed fight(s) as phases of (frames, weapons firing, secondaries firing): each fight's opening
    magazine window with secondaries, the rest of the fight, then a recovery gap (no weapons, full regeneration)."""
    plan = []
    for fight, gap in role.fight_chain or ((role.fight_seconds, 0.0),):
        frames = fight * FPS
        window = magazine_share(fight) * frames
        plan += [(window, True, True), (frames - window, True, False)]
        if gap > 0:
            plan.append((gap * FPS, False, False))
    return plan


def fight_label(role: "Role") -> str:
    if role.fight_chain:
        return "Combat (" + " + ".join(f"{f:.0f} s" for f, _ in role.fight_chain) + ")"
    return f"Combat ({role.fight_seconds:.0f} s)"


def weapon_duty(role: "Role", weapon: "WeaponStats") -> float:
    """Share of a fight this weapon fires: the stage's gun, turret or secondary duty (or a calibration override)."""
    stage = STAGES.get(role.stage, STAGES[DEFAULT_STAGE])
    if weapon.secondary:
        return stage.secondary_share if SECONDARY_SHARE is None else SECONDARY_SHARE
    if PRIMARY_SHARE is not None:
        return PRIMARY_SHARE
    return stage.turret_share if weapon.turret else stage.gun_share


def magazine_share(fight_seconds: float) -> float:
    """MAGAZINE_WINDOW for this fight length: the entry for the nearest listed length (the whole fight if empty)."""
    if not MAGAZINE_WINDOW:
        return 1.0
    key = min(MAGAZINE_WINDOW, key=lambda k: abs(float(k) - fight_seconds))
    return MAGAZINE_WINDOW[key]


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


def projectile_speed(game: GameData, weapon: Weapon, depth: int = 0) -> float:
    """Pixels per frame: velocity (or its override), top speed for accelerating projectiles (acceleration / drag),
    else the fastest submunition (weapons whose projectile is a submunition have no velocity of their own)."""
    stats = weapon.stats
    speed = stats.get("velocity override") or stats.get("velocity", 0.0)
    if stats.get("acceleration", 0) > 0 and stats.get("drag", 0) > 0:
        speed = max(speed, stats["acceleration"] / stats["drag"])
    if speed <= 0 and depth < 10:
        subs = [game.outfits[n].weapon for n, _ in weapon.submunitions
                if n in game.outfits and game.outfits[n].weapon is not None]
        speed = max((projectile_speed(game, s, depth + 1) for s in subs), default=0.0)
    return speed


EFFECT_DAMAGE = ("ion", "scrambling", "heat", "slowing", "disruption", "burn", "corrosion", "leak", "discharge",
                 "energy", "fuel")
LEGACY_TURRET_TURN = 4.0  # Outfit.cpp: a turret with no "turret turn" (not anti-missile or tractor) turns 4°/frame


def _weapon_stats(game: GameData, outfit: Outfit, count: int) -> WeaponStats:
    w = outfit.weapon
    rate = count / max(w.stats.get("reload", 1.0), 1.0)  # average shots per frame, bursts included
    turret = outfit.attributes.get("turret mounts", 0) < 0
    turret_turn = w.stats.get("turret turn", 0.0)
    if turret and not turret_turn and not w.stats.get("anti-missile") and not w.stats.get("tractor beam"):
        turret_turn = LEGACY_TURRET_TURN
    return WeaponStats(
        name=outfit.name, count=count, turret=turret,
        range=weapon_range(game, w), dropoff=w.damage_dropoff,
        dropoff_modifier=w.stats.get("dropoff modifier", 1.0),
        shield_damage=max(0.0, weapon_damage(game, w, "shield damage")) * rate,
        hull_damage=max(0.0, weapon_damage(game, w, "hull damage")) * rate,
        energy=w.stats.get("firing energy", 0.0) * rate,
        heat=w.stats.get("firing heat", 0.0) * rate,
        fuel=w.stats.get("firing fuel", 0.0) * rate,
        hit_force=w.stats.get("hit force", 0.0) * rate,
        anti_missile=w.stats.get("anti-missile", 0.0),
        tractor=w.stats.get("tractor beam", 0.0),
        disruption=weapon_damage(game, w, "disruption damage") * rate,
        piercing=w.stats.get("piercing", 0.0),
        ammo=w.ammo[0] if w.ammo else None,
        ammo_rate=(w.ammo[1] * rate) if w.ammo else 0.0,
        instantaneous=w.stats.get("lifetime", 0.0) <= 1 and not w.submunitions,
        shot_energy=w.stats.get("firing energy", 0.0),
        shots_per_second=FPS / max(w.stats.get("reload", 1.0), 1.0),
        secondary=outfit.category == "Secondary Weapons",
        turret_turn=turret_turn * FPS,
        projectile_speed=projectile_speed(game, w) * FPS,
        homing="homing" in w.flags or w.stats.get("homing", 0) > 0,
        effects={k: v * rate for k in EFFECT_DAMAGE if (v := max(0.0, weapon_damage(game, w, f"{k} damage")))},
        blast_radius=w.stats.get("blast radius", 0.0),
        shot_damage=max(0.0, weapon_damage(game, w, "shield damage")) + max(0.0, weapon_damage(game, w, "hull damage")),
        shot_force=w.stats.get("hit force", 0.0),
        capacity=-outfit.attributes.get("weapon capacity", 0.0) * count,
    )


def build(game: GameData, hull: Hull, outfits: dict[str, int]) -> Ship:
    """Total up a hull and its outfits, and check the game's fit rule."""
    attrs = dict(hull.attributes)
    mass, cost = hull.mass, hull.cost
    weapons: list[WeaponStats] = []
    unknown: list[str] = []
    outfits = {name: count for name, count in outfits.items() if count > 0}
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
    return Ship(hull, dict(outfits), attrs, mass, cost, errors, weapons, unknown,
                {n: game.outfits[n].attributes for n in outfits if n in game.outfits})


@dataclass
class CaptureResult:
    target: str
    passed: bool
    shields_left: float      # target's shield fraction when its hull reaches the disable threshold


def capture_intact(ship: Ship, target: Ship) -> CaptureResult:
    """Can this ship (with 20% help from stock ships) disable the target before its shields drop below half?

    While shields are up, each hit is split (DamageProfile.cpp): shields take shield damage × s and the hull
    takes hull damage × (1 − s), with s = (1 − piercing) / (1 + 0.01 L) for disruption level L, which settles
    at 99 × disruption per frame. Stock ships' damage is taken as non-piercing. Target regeneration is ignored,
    which keeps the check independent of fleet size.
    """
    weapons = [w for w in ship.weapons if w.offensive or w.disruption]
    divisor = 1 + 0.01 * 99 * sum(w.disruption for w in weapons)
    own = sum(w.shield_damage + w.hull_damage for w in weapons)
    stock = own * (1 - CAPTURE_OWN_SHARE) / CAPTURE_OWN_SHARE
    shield_rate = hull_rate = 0.0
    for shield_dmg, hull_dmg, piercing in [(w.shield_damage, w.hull_damage, w.piercing) for w in weapons] + [
            (stock * STOCK_SHIELD_SHARE, stock * (1 - STOCK_SHIELD_SHARE), 0.0)]:
        s = (1 - min(piercing, 1.0)) / divisor
        shield_rate += s * shield_dmg
        hull_rate += (1 - s) * hull_dmg
    shield_rate /= 1 + target.get("shield protection")
    hull_rate /= 1 + target.get("hull protection")
    hull_needed = max(0.0, target.max_hull - target.disable_threshold)
    if hull_rate <= 0:
        return CaptureResult(target.hull.name, False, 0.0)
    shields_left = 1 - shield_rate * hull_needed / hull_rate / target.max_shields if target.max_shields else 1.0
    return CaptureResult(target.hull.name, shields_left >= CAPTURE_SHIELDS_LEFT, max(0.0, shields_left))


def default_capture_targets(game: GameData) -> list[Hull]:
    """Hulls worth farming intact: Pug, Korath, Heliarch, Ka'het and Quarg (by data folder or name), not sold in any
    shipyard, with shields, and not scenery (asteroids, game mechanics) or scrap ("Aberrant" wrecks)."""
    sold = {name for shop in game.shipyards.values() for name in shop.items}
    return [h for h in game.hulls.values()
            if any(f in (h.source + " " + h.name).lower() for f in CAPTURE_FACTIONS)
            and h.name not in sold and not h.deprecated and h.attributes.get("shields", 0) > 0
            and h.category not in ("Fighter", "Drone", "Unclassified", "Unclassified Minor", "Game Mechanics", "")
            and not h.name.startswith(("Aberrant", "Asteroid"))]


def evaluate(ship: Ship, role: Role, disruption_available: bool = False,
             capture_targets: list[Ship] | None = None) -> list[Check]:
    """Check a ship against the design rules in docs/design-notes.md.

    disruption_available: whether any available outfit deals shield disruption (capture-intact goal).
    """
    checks: list[Check] = []
    add = lambda name, passed, detail: checks.append(Check(name, passed, detail))
    s = FPS  # displayed values are per second

    # Hull-type exceptions: carried craft (fighters, drones) don't jump or refuel themselves; interceptors are
    # small and nimble enough to skip some baseline requirements.
    carried = ship.hull.category in CARRIED_CATEGORIES
    interceptor = ship.hull.category == "Interceptor"
    fighter_rules = role.fighter or carried

    add("Fits (game rule)", not ship.fit_errors, "; ".join(ship.fit_errors) or "all capacities within limits")
    if ship.max_shields > 0:
        regen = ship.shield_regen * FPS
        add("Shield refill", None, f"{ship.max_shields / regen:.0f} s" if regen > 0 else "no shield regeneration")
    ratio = turn_accel_ratio(ship)
    if ratio is not None:
        add("Turn to acceleration", None,
            f"{ratio:.3f} (stock 10th–90th percentile {TURN_ACCEL_BAND[0]}–{TURN_ACCEL_BAND[1]}"
            + (f"; score −{turn_accel_penalty(ship):.2f})" if turn_accel_penalty(ship) else ")"))
    add("Can move", ship.get("thrust") > 0 and ship.get("turn") > 0,
        f"thrust {ship.get('thrust'):g}, turn {ship.get('turn'):g}")
    if role.needs_drives and not carried:
        excluded = role.excluded_drives | ({"jump drive"} if interceptor else set())
        wanted = [d for d in ("hyperdrive", "jump drive", "quantum keystone") if d not in excluded]
        missing = [d for d in wanted if not ship.get(d)]
        add("Drives", not missing, "missing: " + ", ".join(missing) if missing else ", ".join(wanted))

    # Energy and heat in each job scenario, at the 90% heat target.
    solar = 0.0 if role.must_run_dark else ship.get("solar collection")
    solar_heat = ship.get("solar heat")
    f_combat, f_stay = solar_factor(role), stay_factor(role)
    weapon_share = 1.0 if role.combat and not fighter_rules else WEAPON_SHARE_NON_COMBAT
    w_energy, w_heat = ship.activity("weapons")
    moves = {m: ship.activity(m) for m in ("regen", "thrust", "turn")}
    if ship.has_torch:
        rest = max(moves["regen"][0], moves["turn"][0]), max(moves["regen"][1], moves["turn"][1])
        # The worse of the two shares: energy made by thrusting only counts at the reduced share.
        move_energy, move_heat = (max(t * moves["thrust"][i] + (1 - t) * rest[i] for t in thrust_shares(ship))
                                  for i in (0, 1))
    else:
        move_energy = max(v[0] for v in moves.values())
        move_heat = max(v[1] for v in moves.values())
    scenarios = []
    if interceptor:
        # Reserves instead of a balance: 90 s at 50% weapons, from idle heat, on batteries.
        load_e = WEAPON_SHARE_NON_COMBAT * w_energy + move_energy
        load_h = WEAPON_SHARE_NON_COMBAT * w_heat + move_heat
        start = ship.equilibrium_heat(ship.idle_heat)
        end = ship.heat_after(ship.idle_heat + load_h + solar_heat * f_combat, INTERCEPTOR_BATTLE_FRAMES, start)
        fraction = end / ship.max_heat if ship.max_heat else math.inf
        net = ship.idle_energy + solar * f_combat - load_e - ship.get("cooling energy") * min(1.0, fraction)
        drain = max(0.0, -net) * INTERCEPTOR_BATTLE_FRAMES
        add("Interceptor reserves: heat for a 90 s battle", fraction <= HEAT_TARGET,
            f"reaches {fraction:.0%} of max heat after 90 s at 50% weapons")
        add("Interceptor reserves: energy for a 90 s battle", drain <= ship.get("energy capacity"),
            f"uses {drain:.0f} stored energy (has {ship.get('energy capacity'):.0f})")
    elif not (role.combat and not fighter_rules):
        scenarios.append(("Weapons in combat", f_combat,
                          weapon_share * w_energy + move_energy, weapon_share * w_heat + move_heat))
    if role.evader:
        cloak = ship.activity("cloak")
        scenarios.append(("Evading (rule 3)", SOLAR_EVADING, cloak[0], cloak[1]))
    thrust = moves["thrust"]
    scenarios.append(("Near a bright star (rule 2b)", f_stay, thrust[0], thrust[1]))

    steady_heat_fraction = 0.0          # heat level before a non-combat ship's burst
    # Every ship, out of combat: cruising indefinitely, and recovering shields and hull (on batteries) after a fight.
    cruise_e, cruise_h = cruise_load(ship)
    if role.cloak_duty:
        cloak_e, cloak_h = ship.activity("cloak")
        cruise_e, cruise_h = cruise_e + role.cloak_duty * cloak_e, cruise_h + role.cloak_duty * cloak_h
    cooling_e = ship.get("cooling energy")
    base_net = ship.idle_energy + solar * f_combat - cruise_e
    cruise_in = ship.idle_heat + cruise_h + solar_heat * f_combat
    cruise_heat = ship.equilibrium_heat(cruise_in)
    cruise_fraction = cruise_heat / ship.max_heat if ship.max_heat else math.inf
    cruise_net = base_net - cooling_e * min(1.0, cruise_fraction)
    add("Cruising: heat", cruise_fraction <= HEAT_TARGET,
        f"settles at {cruise_fraction:.0%} of max heat (thrust 70%, turn 30%, idle draw)")
    add("Cruising: energy", cruise_net >= 0, f"net {cruise_net * s:+.0f}/s (solar ×{f_combat:.2f}"
        + (f", cloaked {role.cloak_duty:.0%} of the time)" if role.cloak_duty else ")"))
    start_heat = min(cruise_heat, ship.max_heat) if math.isfinite(cruise_heat) else ship.max_heat
    (shield_e, shield_h), (hull_e, hull_h) = ((ship._regen_cost(k, "energy"), ship._regen_cost(k, "heat"))
                                              for k in ("shield", "hull"))
    t_shields, t_hull = regen_times(ship)
    if t_shields or t_hull:
        worst = None
        for long_shields in (True, False):
            ts = (t_shields or 0.0) * (RECOVERY_LONG if long_shields else 1.0)
            th = (t_hull or 0.0) * (1.0 if long_shields else RECOVERY_LONG)
            both, rest = min(ts, th), abs(ts - th)
            rest_e, rest_h = (shield_e, shield_h) if ts > th else (hull_e, hull_h)
            draw = cooling_e        # cooling at full power: conservative
            low, peak = run_phases(ship, [
                (both, base_net - draw - shield_e - hull_e, cruise_in + shield_h + hull_h),
                (rest, base_net - draw - rest_e, cruise_in + rest_h)], start_heat)
            margin = (low, -peak)
            if worst is None or margin < worst[0]:
                worst = (margin, low, peak, ts, th)
        _, low, peak, ts, th = worst
        fraction = peak / ship.max_heat if ship.max_heat else math.inf
        add("Recovery: shields and hull", low >= 0 and fraction <= HEAT_TARGET,
            f"lowest stored energy {low:.0f} of {ship.get('energy capacity'):.0f}, peak heat {fraction:.0%} "
            f"(shields {ts / FPS:.0f} s, hull {th / FPS:.0f} s)")

    # Combat ships: the designed fight(s) on batteries, from cruising heat (or hot).
    if role.combat and not fighter_rules and not interceptor:
        primary_e = sum(weapon_duty(role, w) * w.energy for w in ship.weapons if not w.secondary)
        primary_h = sum(weapon_duty(role, w) * w.heat for w in ship.weapons if not w.secondary)
        secondary_e = sum(weapon_duty(role, w) * w.energy for w in ship.weapons if w.secondary)
        secondary_h = sum(weapon_duty(role, w) * w.heat for w in ship.weapons if w.secondary)
        longest = max((f for f, _ in role.fight_chain), default=role.fight_seconds) * FPS
        shields_suffice = t_shields is not None and t_shields <= SHIELD_SELF_SUFFICIENT * longest
        regen_e = shield_e + (0.0 if shields_suffice else hull_e)
        regen_h = shield_h + (0.0 if shields_suffice else hull_h)
        phases = []
        for frames, firing, secondaries in combat_plan(role):
            if firing:
                net = base_net - cooling_e - primary_e - regen_e - (secondary_e if secondaries else 0.0)
                heat_in = cruise_in + primary_h + regen_h + (secondary_h if secondaries else 0.0)
            else:
                net = base_net - cooling_e - shield_e - hull_e
                heat_in = cruise_in + shield_h + hull_h
            phases.append((frames, net, heat_in))
        fight_start = start_heat
        if role.start_state == "hot":
            hot = ship.equilibrium_heat(ship.idle_heat + ship.activity("thrust")[1] + solar_heat * f_stay)
            fight_start = min(max(hot, start_heat), ship.max_heat)
        low, peak = run_phases(ship, phases, fight_start)
        fraction = peak / ship.max_heat if ship.max_heat else math.inf
        label = fight_label(role)
        add(f"{label}: heat", fraction <= HEAT_TARGET,
            f"peaks at {fraction:.0%} of max heat ({role.stage} duty, "
            f"{'shield' if shields_suffice else 'shield and hull'} regen"
            + (", starting hot)" if role.start_state == "hot" else ")"))
        add(f"{label}: energy", low >= 0,
            f"lowest stored energy {low:.0f} of {ship.get('energy capacity'):.0f}")
        # Batteries empty: generation carries movement, cooling and shield regen, plus part of the weapon fire.
        spare = base_net - cooling_e - shield_e
        fire = primary_e + secondary_e
        buffer = ship.get("energy capacity") + ship.idle_energy + solar * f_combat
        minimum = batteryless_minimum(ship.weapons, role, buffer)
        share = spare / fire if fire > 0 else math.inf
        if fire <= 0:
            detail = "no weapons to fire"
        elif not math.isfinite(minimum):
            detail = (f"energy storage {buffer:.0f}: too few weapons have a shot that fits "
                      f"(needs {BATTERYLESS_WEAPONS + (1 if sum(w.count for w in ship.weapons if w.offensive) > BATTERYLESS_MANY else 0)})")
        else:
            detail = (f"generation carries {min(share, 9.99):.0%} of the weapon fire with batteries empty (needs "
                      f"{BATTERYLESS_SHARE:.0%}, and at least {minimum * FPS:.0f}/s for the cheapest weapons whose shot "
                      f"fits in storage)")
        add("Combat without batteries", spare >= max(BATTERYLESS_SHARE * fire, minimum), detail)

    # Cloaked most of the time (N26): needs a cloak, and fuel income that keeps up with cloaking.
    if role.cloak_duty:
        add("Cloak", ship.get("cloak") > 0, f"cloak {ship.get('cloak'):g}" if ship.get("cloak") > 0
            else "this hull can't cloak and no cloaking outfit is fitted")
        burn = role.cloak_duty * ship.get("cloaking fuel")
        income = 0.03 * WIND_COMBAT * math.sqrt(max(0.0, ship.get("ramscoop"))) + ship.get("fuel generation")
        add("Cloak: fuel keeps up", income >= burn,
            f"cloaking burns {burn * s:.2f} fuel/s at {role.cloak_duty:.0%}, income {income * s:.2f}/s")
    # Exposure window (N27): survive this long uncloaked under the war zone's fire.
    if role.exposure_seconds and role.exposure_dps:
        margin = exposure_margin(ship, role)
        add(f"Exposure: {role.exposure_seconds:.0f} s under fire", margin >= 1.0,
            f"{margin:.2f} × what {role.exposure_dps:.0f} damage/s for {role.exposure_seconds:.0f} s takes")

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

    if not (role.combat and not fighter_rules) and not interceptor:
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
    if role.needs_ramscoop and not (carried or interceptor):
        add("Ramscoop (rule 1)", ramscoop > 0, f"ramscoop {ramscoop:g}")
    jumps = ship.jumps
    if role.long_range and ship.average_jump_fuel:
        wind = BEST_WIND[min(max(jumps, 1), 9)]
        per_frame = 0.03 * wind * REFUEL_SCALE * math.sqrt(ramscoop) + ship.get("fuel generation")
        seconds = ship.average_jump_fuel / per_frame / 180 if per_frame else math.inf
        add("Refuel one jump (rule 2)", seconds <= 2.0,
            f"{seconds:.1f} s of fast-forward with {jumps} jumps of fuel (best wind {wind})")
    # A trip: jump in, fight, jump out, with ramscoop recovery during the fight counted far from the star.
    fight_fuel = 0.0
    frames = role.fight_seconds * FPS
    if role.combat and ship.has_torch:
        fight_fuel += CRUISE_THRUST * ship.get("thrusting fuel") * frames
    if role.combat and not role.hero and ship.get("afterburner thrust"):
        fight_fuel += 0.10 * ship.get("afterburner fuel") * frames
    if role.combat and ship.average_jump_fuel and role.needs_drives:
        recovery = (0.03 * WIND_COMBAT * math.sqrt(ramscoop) + ship.get("fuel generation")) * frames
        trip = 2 * ship.average_jump_fuel + max(0.0, fight_fuel - recovery)
        add("Fuel for a trip", ship.get("fuel capacity") >= trip,
            f"needs {trip:.0f} (jump in and out {2 * ship.average_jump_fuel:.0f} + {fight_fuel:.0f} burned in the "
            f"fight − {min(recovery, fight_fuel):.0f} recovered), has {ship.get('fuel capacity'):.0f}")
        # Back to full at a typical staging star, sitting close to it, within the player's patience.
        limit = PATIENCE.get(role.patience, PATIENCE["routine"])
        rate = 0.03 * STAGING_WIND * REFUEL_SCALE * math.sqrt(ramscoop) + ship.get("fuel generation")
        seconds = trip / rate / FPS if rate > 0 else math.inf
        if role.needs_ramscoop:
            add("Refuel at staging", seconds <= limit,
                f"{seconds:.0f} s to recover {trip:.0f} fuel at a typical staging star (wind {STAGING_WIND}), "
                f"patience {limit:.0f} s ({role.patience})")
        t_s, t_h = regen_times(ship)
        add("Recover at staging (shields, hull)", None,
            f"shields {(t_s or 0) / FPS:.0f} s, hull from the disable line {(t_h or 0) / FPS:.0f} s "
            f"(patience {limit:.0f} s; not enforced yet)")
    # Fuel-burning thrusters on AI-flown combat ships: the AI never holds fuel back for them.
    if role.combat and not role.hero and ship.get("thrusting fuel") > 0:
        burn = CRUISE_THRUST * ship.get("thrusting fuel")
        income = 0.03 * WIND_COMBAT * math.sqrt(ramscoop) + ship.get("fuel generation")
        if TORCH_ESCORTS:
            add("Fuel thrusters keep up (AI-flown)", income >= burn,
                f"thrusting burns {burn * FPS:.1f} fuel/s while maneuvering, income {income * FPS:.1f}/s away from "
                f"the star")
        else:
            add("No fuel thrusters (AI-flown)", False, "fuel-burning thrusters are off for AI-flown ships")

    # Magazine depth: ammo for the weapons' share of each fight, for the fights between restocks.
    needed: dict[str, float] = {}
    for w in ship.weapons:
        if w.ammo and not w.ammo_rate:
            # "ammo X 0": the weapon only fires if X is installed, and doesn't use it up.
            add(f"Requires: {w.ammo} (for {w.name})", ship.outfits.get(w.ammo, 0) >= 1,
                "installed" if ship.outfits.get(w.ammo, 0) else "not installed")
        elif w.ammo:
            frames = role.fight_seconds * FPS * magazine_window(w, role.fight_seconds) * weapon_duty(role, w)
            needed[w.ammo] = needed.get(w.ammo, 0.0) + w.ammo_rate * frames * role.fights_per_restock
    for ammo, need in needed.items():
        have = ship.outfits.get(ammo, 0)
        add(f"Magazine: {ammo}", have >= need,
            f"carries {have}, needs {math.ceil(need)} for {role.fights_per_restock} fights")

    # Ship::FlightCheck "insufficient energy to fire?": a weapon only fires if one shot's energy fits in the energy
    # capacity plus one frame of net generation (the "surge" when there is no battery). Solar at combat strength.
    surge = ship.get("energy capacity") + ship.idle_energy + solar * f_combat
    starved = [w.name for w in ship.weapons if w.shot_energy > surge]
    if ship.weapons:
        add("Energy per shot", not starved,
            f"can't fire (one shot needs more than {surge:.1f}): " + ", ".join(starved) if starved
            else f"every shot fits in {surge:.1f} (energy capacity + one frame of generation)")
    if role.needs_regen:
        regen = ship.shield_regen + ship.hull_repair
        add("Regeneration", regen > 0, f"shield {ship.shield_regen * s:.1f}/s, hull {ship.hull_repair * s:.1f}/s"
            if regen > 0 else "no shield generation and no hull repair")

    if role.needs_anti_missile and not (fighter_rules or interceptor):
        has_am = any(w.anti_missile for w in ship.weapons)
        add("Anti-missile", has_am, "has anti-missile" if has_am else "no anti-missile turret")
    if role.goal == "capture-intact":
        slow = [w.name for w in ship.weapons if w.offensive and not w.instantaneous]
        add("Capture-intact: instantaneous weapons only", not slow,
            "non-instantaneous: " + ", ".join(slow) if slow else "all damage weapons are instantaneous")
        if disruption_available and capture_targets:
            results = [capture_intact(ship, t) for t in capture_targets]
            failed = [r for r in results if not r.passed]
            worst = min(results, key=lambda r: r.shields_left)
            add("Capture-intact: disabled with shields ≥ 50%", not failed,
                f"{len(results) - len(failed)} of {len(results)} targets; worst {worst.target} "
                f"at {worst.shields_left:.0%} shields")
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
