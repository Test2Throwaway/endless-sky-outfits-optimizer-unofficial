"""Strict-dominance pruning of the candidate pool.

An outfit is dropped only if another candidate is at least as good in every way, so the drop is valid for every
request the optimizer can be given: it never trades one stat against another. It runs on the pool `candidates()`
has already filtered to this user's availability, so the outfit that beats a dropped one is always available.

B beats A when all of these hold:
- same category;
- every attribute (and weapon stat) with a known direction is at least as good on B and strictly better on one;
- presence attributes (a class a role can forbid or that changes what the outfit is, e.g. solar, afterburner,
  ion damage) are present on both or on neither;
- every other attribute is equal, so attributes nobody has classified never let one outfit beat another;
- weapon flags, ammunition, submunitions and damage dropoff are identical;
- B has no tighter copy limit.

Whole copies: a ship's attributes are the sum of its outfits', so k copies of B (k ≥ 2) beat one A when the scaled
attributes pass the same test and B's copy limit allows k. That catches "two small thrusters beat one big one". Not
for weapons: each copy needs its own gun port or turret mount, which already fails the capacity test, and weapon stats
don't add up.

Kept regardless: outfits with nothing but a footprint (space, mass, crew), whose value is their identity (missions ask
for a Brig by name); outfits the user explicitly allowed by name. Price is ignored: designs are never scored on cost.

Found by the sheet-calc obsolescence tool (Test2Throwaway/endless-sky-sheet-calc), which also has the planned
smarter layers: power and cooling per solar case, then engines, regeneration and weapons at traded prices.
"""

from __future__ import annotations

from dataclasses import dataclass

from .availability import Availability
from .gamedata import Outfit

# Capacities are negative when used, so "less used" is higher.
HIGHER = {
    "outfit space", "cargo space", "weapon capacity", "engine capacity", "gun ports", "turret mounts",
    "reactor upgrades", "relay upgrades", "nanite upgrades", "solar cell", "shield connection point",
    "anchor point", "spinal mount", "multimodal armor", "asteroid mount small", "asteroid mount jd", "lasing power",
    "energy generation", "energy capacity", "solar collection", "cooling", "active cooling", "heat dissipation",
    "heat capacity",
    "thrust", "turn", "reverse thrust", "afterburner thrust", "drag reduction", "inertia reduction",
    "shield generation", "hull repair rate", "delayed shield generation",
    "fuel capacity", "fuel generation", "ramscoop", "jump range", "jump speed",
    "bunks", "crew equivalent", "tactical scan power", "asteroid scan power", "cargo scan power",
    "cargo scan efficiency", "outfit scan power", "outfit scan efficiency", "atmosphere scan", "radar jamming",
    "optical jamming", "scan interference", "cargo scan opacity", "outfit scan opacity", "holographic entertainment",
}
LOWER = {
    "mass", "required crew", "heat generation", "energy consumption", "solar heat", "cooling energy",
    "thrusting energy", "thrusting heat", "thrusting fuel", "turning energy", "turning heat",
    "reverse thrusting energy", "reverse thrusting heat", "afterburner energy", "afterburner heat", "afterburner fuel",
    "afterburner shields", "shield energy", "shield heat", "shield fuel", "hull energy", "hull heat",
    "delayed shield energy", "delayed shield heat", "shield delay", "depleted shield delay",
    "hyperdrive fuel", "jump drive fuel", "drag", "overheat damage rate", "scan brightness", "operating costs",
}
# Every "<x> protection" and "<x> resistance" is higher-is-better; every other "<x> capacity" is ammunition storage
# (a launcher provides it, ammunition uses it), also higher-is-better.
HIGHER_SUFFIXES = (" protection", " resistance", " capacity")
IGNORED = {"index", "unplunderable", "flotsam chance"}
PRESENCE = {
    "solar collection", "ramscoop", "afterburner thrust", "thrusting fuel", "cloak", "illegal", "atrocity",
    "automaton", "hyperdrive", "jump drive", "scram drive", "quantum keystone", "bunks",
}
# Attributes that only say how much room an outfit takes: an outfit with nothing else is kept.
FOOTPRINT = {"outfit space", "cargo space", "weapon capacity", "engine capacity", "mass", "required crew"}

WEAPON_HIGHER = {
    "shield damage", "hull damage", "heat damage", "ion damage", "scrambling damage", "slowing damage",
    "disruption damage", "discharge damage", "corrosion damage", "leak damage", "burn damage", "energy damage",
    "fuel damage", "minable damage", "prospecting", "anti-missile", "tractor beam",
    "velocity", "lifetime", "range override", "velocity override", "turret turn",
}
WEAPON_LOWER = {
    "reload", "firing energy", "firing heat", "firing fuel", "firing hull", "firing shields", "firing ion",
    "relative firing shields", "inaccuracy",
}
WEAPON_PRESENCE = {
    "heat damage", "ion damage", "scrambling damage", "slowing damage", "disruption damage", "discharge damage",
    "corrosion damage", "leak damage", "burn damage", "energy damage", "fuel damage", "minable damage", "prospecting",
    "anti-missile", "tractor beam", "firing fuel", "firing hull", "firing shields", "firing ion",
    "relative firing shields",
}
# The game's values for weapon stats that aren't 0 when absent (Weapon.h, Outfit.cpp).
WEAPON_DEFAULTS = {"reload": 1.0}
TURRET_TURN_DEFAULT = 4.0   # per frame (240°/s), for turrets that aren't anti-missile or tractor beams

# One per crew member, so k copies aren't k times as good. (Hand to Hand is excluded from the pool today anyway.)
NOT_SCALABLE = {"Hand to Hand"}
MAX_COPIES = 10


def _direction(key: str) -> int | None:
    """+1 higher is better, -1 lower is better, 0 ignored, None must be equal."""
    if key in IGNORED:
        return 0
    if key in HIGHER or key.endswith(HIGHER_SUFFIXES):
        return 1
    if key in LOWER:
        return -1
    return None


def _weapon_direction(key: str) -> int | None:
    if key in WEAPON_HIGHER:
        return 1
    if key in WEAPON_LOWER:
        return -1
    return None


@dataclass
class _Candidate:
    outfit: Outfit
    attrs: dict[str, float]
    weapon_stats: dict[str, float] | None
    weapon_shape: tuple | None      # flags, ammo, submunitions, dropoff: must be identical
    copy_limit: float               # inf when unlimited

    @property
    def name(self) -> str:
        return self.outfit.name


def _candidate(outfit: Outfit, limit: int | None) -> _Candidate:
    attrs = {k: v for k, v in outfit.attributes.items() if _direction(k) != 0}
    attrs["mass"] = outfit.mass
    stats = shape = None
    if outfit.weapon is not None:
        w = outfit.weapon
        stats = dict(WEAPON_DEFAULTS) | dict(w.stats)
        if (outfit.category == "Turrets" and not stats.get("turret turn") and not stats.get("anti-missile")
                and not stats.get("tractor beam")):
            stats["turret turn"] = TURRET_TURN_DEFAULT
        shape = (frozenset(w.flags), w.ammo, tuple(w.submunitions), w.damage_dropoff)
    copy_limit = float("inf") if limit is None else float(limit)
    return _Candidate(outfit, attrs, stats, shape, copy_limit)


def _compare(a: dict[str, float], b: dict[str, float], direction, presence) -> bool | None:
    """None if b can't beat a; otherwise whether b is strictly better somewhere."""
    strictly = False
    for key in a.keys() | b.keys():
        d = direction(key)
        if d == 0:
            continue
        va, vb = a.get(key, 0.0), b.get(key, 0.0)
        if key in presence and bool(va) != bool(vb):
            return None
        if d is None:
            if va != vb:
                return None
            continue
        if d * (vb - va) < -1e-9:
            return None
        if d * (vb - va) > 1e-9:
            strictly = True
    return strictly


def _same_kind(a: _Candidate, b: _Candidate) -> bool:
    oa, ob = a.outfit, b.outfit
    return (oa.category == ob.category and sorted(oa.ammo) == sorted(ob.ammo) and sorted(oa.linked) == sorted(ob.linked)
            and a.weapon_shape == b.weapon_shape and (a.weapon_stats is None) == (b.weapon_stats is None))


def _beats(b: _Candidate, a: _Candidate) -> bool:
    """b is at least as good as a in every way and strictly better somewhere, or identical and wins the tie-break."""
    if not _same_kind(a, b) or b.copy_limit < a.copy_limit:
        return False
    strictly = _compare(a.attrs, b.attrs, _direction, PRESENCE)
    if strictly is None:
        return False
    if a.weapon_stats is not None:
        w = _compare(a.weapon_stats, b.weapon_stats, _weapon_direction, WEAPON_PRESENCE)
        if w is None:
            return False
        strictly = strictly or w
    return strictly or (-b.copy_limit, b.name) < (-a.copy_limit, a.name)


def _copies_to_beat(b: _Candidate, a: _Candidate) -> int | None:
    """The fewest copies k ≥ 2 of b that beat one a, or None."""
    if not _same_kind(a, b) or a.weapon_stats is not None or a.outfit.category in NOT_SCALABLE:
        return None
    space_a, space_b = -a.attrs.get("outfit space", 0.0), -b.attrs.get("outfit space", 0.0)
    if space_b <= 0:
        return None
    for k in range(2, min(MAX_COPIES, int(space_a // space_b)) + 1):
        if k > b.copy_limit:
            return None
        if _compare(a.attrs, {key: v * k for key, v in b.attrs.items()}, _direction, PRESENCE):
            return k
    return None


def _identity_only(c: _Candidate) -> bool:
    return c.weapon_stats is None and all(k in FOOTPRINT for k, v in c.attrs.items() if v)


def prune_obsolete(pool: list[Outfit], available: Availability) -> tuple[list[Outfit], dict[str, str]]:
    """Kept outfits (in pool order), and {dropped outfit: what beats it}."""
    candidates = [_candidate(o, available.copy_limit(o)) for o in pool]
    allowed = available.settings.allowed_outfits
    by_category: dict[str, list[_Candidate]] = {}
    for c in candidates:
        by_category.setdefault(c.outfit.category, []).append(c)
    dropped: dict[str, str] = {}
    for group in by_category.values():
        for a in group:
            if a.name in allowed or _identity_only(a):
                continue
            beaters = []
            for b in group:
                if b is a:
                    continue
                if _beats(b, a):
                    beaters.append(b.name)
                elif (k := _copies_to_beat(b, a)) is not None:
                    beaters.append(f"{k} × {b.name}")
            if beaters:
                dropped[a.name] = "beaten by " + ", ".join(sorted(beaters))
    return [o for o in pool if o.name not in dropped], dropped
