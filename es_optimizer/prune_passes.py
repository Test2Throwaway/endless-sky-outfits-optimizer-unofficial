"""Pruning passes after strict dominance: engines, regeneration and weapon lenses.

Ported from the sheet-calc pruner (Test2Throwaway/endless-sky-sheet-calc: engines.py, regen.py, weapons.py).
Each pass drops an outfit only if another candidate in the same category is at least as good on everything that
pass compares, so the optimizer never loses a design it would prefer.

Engines and regeneration (compensated dominance): every ship pays for its outfits' energy and heat with power plant
and cooling, so outfit space, steady power (energy generation and consumption, heat generation) and the energy and
heat used while thrusting, turning or regenerating are traded at a rate in outfit space per energy/s and per
heat/s. Everything else uses the strict rules of prune.py, so an outfit that also does something else (energy
storage, slots, protection, multipliers) is only beaten by one that does at least as much of it. A drop must hold

- at the lowest and highest rate of each resource over four reference ship sizes, light to capital;
- with each duty (thrust, turn, regeneration) at 0% and at 100%, independently. The cost is linear in each duty,
  so it then holds at every duty in between.

The rates come from sheet calc's power plant search, one set per solar case. A request uses the case that matches
its solar checks: dark when it must run dark, evader for evaders, otherwise normal.

Weapon lenses: strict dominance on only the stats one kind of request cares about.

- damage: regular fighting weapons (shield or hull damage, not anti-missile or tractor beams), for every request
  except capture-intact. Compared: shield and hull damage per second (a
  splitting shot counts 80% of its final submunitions), firing costs per second, median velocity (or velocity
  override), range (range override, else median velocity × median total lifetime), inaccuracy, projectile turn,
  homing, missile strength, turret turn, ammo used per second (same ammunition only; needing none is better),
  and push or pull force per second when the request scores them. Ignored: effect damages, piercing, tracking, blast and trigger radius, penetration, fire timing.
- anti-missile: anti-missile turrets, only against each other, for every request. Compared: strength, shots per
  second, range, firing energy and heat per second, ammo as above.

Both lenses also require the winner to be no worse on what this optimizer scores for a weapon (calculator
WeaponStats): shield and hull damage, shots per second, energy per shot, projectile speed, range, turret turn,
magazine window and damage dropoff. That keeps a lens from dropping a weapon the optimizer would pick.
"""

from __future__ import annotations

from itertools import product

from . import calculator
from .availability import Availability
from .gamedata import GameData, Outfit
from .prune import MAX_COPIES, PRESENCE, _Candidate, _candidate, _compare, _direction

FPS = 60.0
DUTIES = (0.0, 1.0)

# Outfit space per energy/s and per heat/s, from sheet calc's power plant search at four reference ship loads
# (energy draw/s, heat/s): light (150, 800), medium (400, 2000), heavy (1000, 5000), capital (2500, 10000).
# Regenerate with `python -m sheetcalc.prune` there (reports/pruned.json, "power" → case → "prices").
RATES = {
    "dark": [(0.1333, 0.00583), (0.0767, 0.00567), (0.0920, 0.00733), (0.0800, 0.00740)],
    "evader": [(0.1378, 0.00667), (0.0767, 0.00567), (0.0920, 0.00733), (0.0800, 0.00740)],
    "normal": [(0.1244, 0.00750), (0.0767, 0.00567), (0.0920, 0.00733), (0.0800, 0.00740)],
}

# Traded attribute -> (resource, per-second weight, duty group or None for always on).
STEADY_POWER = {
    "energy consumption": ("energy", FPS, None),
    "energy generation": ("energy", -FPS, None),
    "heat generation": ("heat", FPS, None),
}
ENGINE_TRADED = {
    "thrusting energy": ("energy", FPS, "thrust"),
    "thrusting heat": ("heat", FPS, "thrust"),
    "turning energy": ("energy", FPS, "turn"),
    "turning heat": ("heat", FPS, "turn"),
    **STEADY_POWER,
}
REGEN_TRADED = {
    "shield energy": ("energy", FPS, "regen"),
    "shield heat": ("heat", FPS, "regen"),
    "delayed shield energy": ("energy", FPS, "regen"),
    "delayed shield heat": ("heat", FPS, "regen"),
    "hull energy": ("energy", FPS, "regen"),
    "hull heat": ("heat", FPS, "regen"),
    **STEADY_POWER,
}
REGEN_KEYS = {"shield generation", "delayed shield generation", "hull repair rate", "delayed hull repair rate",
              "shield energy multiplier", "shield generation multiplier", "hull repair multiplier",
              "hull energy multiplier", *REGEN_TRADED} - set(STEADY_POWER)

SUBMUNITION_HIT_RATE = 0.8
# Hit force counts in the damage lens only for requests that score it: push (positive) or pull (negative).
HIT_FORCE_METRICS = {"push force": 1.0, "pull force": -1.0}


def solar_case(role: calculator.Role) -> str:
    if role.must_run_dark:
        return "dark"
    return "evader" if role.evader else "normal"


def corners(case: str, traded: dict) -> list[tuple[float, float, dict]]:
    """(energy rate, heat rate, {duty group: duty}) at every corner of the rate box and the duty ends."""
    energy = [e for e, _ in RATES[case]]
    heat = [h for _, h in RATES[case]]
    groups = sorted({g for _, _, g in traded.values() if g})
    duties = [dict(zip(groups, d)) for d in product(DUTIES, repeat=len(groups))]
    return list(product((min(energy), max(energy)), (min(heat), max(heat)), duties))


def _costs(attrs: dict[str, float], at: list, traded: dict) -> list[float]:
    space = -attrs.get("outfit space", 0.0)
    out = []
    for energy_rate, heat_rate, duty in at:
        rate = {"energy": energy_rate, "heat": heat_rate}
        out.append(space + sum(attrs.get(k, 0.0) * w * (duty[g] if g else 1.0) * rate[r]
                               for k, (r, w, g) in traded.items()))
    return out


def _compensated(a: _Candidate, b_attrs: dict[str, float], at: list, traded: dict) -> bool | None:
    """None if b can't beat a; otherwise whether b is strictly better somewhere."""
    untraded = lambda attrs: {k: v for k, v in attrs.items() if k not in traded and k != "outfit space"}
    rest = _compare(untraded(a.attrs), untraded(b_attrs), _direction, PRESENCE)
    if rest is None:
        return None
    ca, cb = _costs(a.attrs, at, traded), _costs(b_attrs, at, traded)
    if any(y > x + 1e-9 for x, y in zip(ca, cb)):
        return None
    return rest or any(y < x - 1e-9 for x, y in zip(ca, cb))


def compensated_dominance(group: list[_Candidate], at: list, traded: dict) -> dict[str, str]:
    """{dropped outfit: "beaten by ..."} within each category of `group`; whole copies count."""
    dropped: dict[str, str] = {}
    for a in group:
        beaters = []
        for b in group:
            if b is a or b.outfit.category != a.outfit.category:
                continue
            if b.copy_limit >= a.copy_limit:
                result = _compensated(a, b.attrs, at, traded)
                if result or (result is False and (-b.copy_limit, b.name) < (-a.copy_limit, a.name)):
                    beaters.append(b.name)
                    continue
            space_a, space_b = -a.attrs.get("outfit space", 0.0), -b.attrs.get("outfit space", 0.0)
            if space_b <= 0:
                continue
            for k in range(2, min(MAX_COPIES, int(space_a // space_b)) + 1):
                if k > b.copy_limit:
                    break
                if _compensated(a, {key: v * k for key, v in b.attrs.items()}, at, traded):
                    beaters.append(f"{k} × {b.name}")
                    break
        if beaters:
            dropped[a.name] = "beaten by " + ", ".join(sorted(beaters))
    return dropped


# --- Weapon lenses ---

def _sub_weapons(game: GameData, weapon) -> list:
    return [(game.outfits[n].weapon, count) for n, count in weapon.submunitions
            if n in game.outfits and game.outfits[n].weapon is not None]


def _final_damage(game: GameData, weapon, key: str, depth: int = 0) -> float:
    subs = _sub_weapons(game, weapon) if depth < 10 else []
    if not subs:
        return weapon.stats.get(key, 0.0)
    return sum(count * _final_damage(game, w, key, depth + 1) for w, count in subs)


def _median_lifetime(game: GameData, weapon, depth: int = 0) -> float:
    subs = _sub_weapons(game, weapon) if depth < 10 else []
    own = weapon.stats.get("lifetime", 0.0) + 0.5 * weapon.stats.get("random lifetime", 0.0)
    return own + max((_median_lifetime(game, w, depth + 1) for w, _ in subs), default=0.0)


def _velocity(weapon) -> float:
    s = weapon.stats
    return s.get("velocity override") or s.get("velocity", 0.0) + 0.5 * s.get("random velocity", 0.0)


def _range(game: GameData, weapon) -> float:
    return weapon.stats.get("range override") or _velocity(weapon) * _median_lifetime(game, weapon)


def _damage_stats(game: GameData, outfit: Outfit, forces=()) -> dict[str, tuple[float, int]] | None:
    w = outfit.weapon
    s = w.stats
    if s.get("anti-missile") or s.get("tractor beam"):
        return None
    rate = FPS / max(1.0, s.get("reload", 1.0))
    split = bool(_sub_weapons(game, w))
    damage = lambda key: SUBMUNITION_HIT_RATE * _final_damage(game, w, key) if split else s.get(key, 0.0)
    stats = {f"{key} /s": (damage(key) * rate, 1) for key in ("shield damage", "hull damage")}
    if not any(v for v, _ in stats.values()):
        return None
    for key in ("firing energy", "firing heat", "firing force", "firing fuel", "firing ion", "firing hull",
                "relative firing shields"):
        stats[f"{key} /s"] = (s.get(key, 0.0) * rate, -1)
    stats |= {"velocity": (_velocity(w), 1), "range": (_range(game, w), 1), "inaccuracy": (s.get("inaccuracy", 0.0), -1),
              "turn": (s.get("turn", 0.0), 1), "homing": (1.0 if s.get("homing") or "homing" in w.flags else 0.0, 1),
              "missile strength": (s.get("missile strength", 0.0), 1)}
    if outfit.category == "Turrets":
        stats["turret turn"] = (s.get("turret turn") or 4.0, 1)
    if w.ammo:
        stats["ammo /s"] = (w.ammo[1] * rate, -1)
    for metric in forces:    # as the optimizer counts it: the weapon's own hit force, per second
        stats[f"{metric} /s"] = (max(0.0, HIT_FORCE_METRICS[metric] * s.get("hit force", 0.0)) * rate, 1)
    return stats


def _anti_missile_stats(game: GameData, outfit: Outfit) -> dict[str, tuple[float, int]] | None:
    w = outfit.weapon
    s = w.stats
    if not s.get("anti-missile"):
        return None
    rate = FPS / max(1.0, s.get("reload", 1.0))
    stats = {"anti-missile": (s["anti-missile"], 1), "shots /s": (rate, 1), "range": (_range(game, w), 1),
             "firing energy /s": (s.get("firing energy", 0.0) * rate, -1),
             "firing heat /s": (s.get("firing heat", 0.0) * rate, -1)}
    if w.ammo:
        stats["ammo /s"] = (w.ammo[1] * rate, -1)
    return stats


def _optimizer_view(game: GameData, outfit: Outfit) -> dict[str, tuple[float, int]]:
    """What the optimizer scores for one copy of a weapon, with directions."""
    w = calculator._weapon_stats(game, outfit, 1)
    view = {"shield damage": (w.shield_damage, 1), "hull damage": (w.hull_damage, 1),
            "shots /s": (w.shots_per_second, 1), "energy per shot": (w.shot_energy, -1),
            "projectile speed": (w.projectile_speed, 1), "range": (w.range, 1),
            "magazine window": (calculator.magazine_window(w, 240.0) + calculator.magazine_window(w, 90.0), 1)}
    if w.turret and not w.homing:
        view["turret turn"] = (w.turret_turn, 1)
    return view


def _at_least(a: dict, b: dict) -> bool | None:
    """None if b is worse than a anywhere; otherwise whether b is strictly better somewhere."""
    strictly = False
    for key in a.keys() | b.keys():
        d = (a.get(key) or b[key])[1]
        va, vb = a.get(key, (0.0, d))[0], b.get(key, (0.0, d))[0]
        if d * (vb - va) < -1e-9:
            return None
        strictly = strictly or d * (vb - va) > 1e-9
    return strictly


def lens_dominance(game: GameData, group: list[_Candidate], stats_of) -> dict[str, str]:
    entries = []
    for c in group:
        if c.outfit.weapon is None or (stats := stats_of(game, c.outfit)) is None:
            continue
        w = c.outfit.weapon
        entries.append((c, stats, _optimizer_view(game, c.outfit), w.ammo[0] if w.ammo else None, w.damage_dropoff))
    dropped: dict[str, str] = {}
    for a, sa, va, ammo_a, drop_a in entries:
        beaters = []
        for b, sb, vb, ammo_b, drop_b in entries:
            if b is a or b.outfit.category != a.outfit.category or b.copy_limit < a.copy_limit:
                continue
            if (ammo_b is not None and ammo_b != ammo_a) or drop_b != drop_a:
                continue
            top = _compare(a.attrs, b.attrs, _direction, PRESENCE)
            lens = _at_least(sa, sb)
            view = _at_least(va, vb)
            if top is None or lens is None or view is None:
                continue
            if top or lens or view or (ammo_b is None and ammo_a is not None) or (-b.copy_limit, b.name) < (
                    -a.copy_limit, a.name):
                beaters.append(b.name)
        if beaters:
            dropped[a.name] = "beaten by " + ", ".join(sorted(beaters))
    return dropped


def scored_forces(request) -> list[str]:
    used = set(request.metrics) | set(request.must_min) | set(request.must_max)
    return sorted(used & set(HIT_FORCE_METRICS))


def prune_passes(game: GameData, pool: list[Outfit], available: Availability, request) -> tuple[list[Outfit],
                                                                                                dict[str, str]]:
    """Kept outfits (in pool order), and {dropped outfit: what beats it, with the pass that dropped it}."""
    allowed = available.settings.allowed_outfits
    group = [_candidate(o, available.copy_limit(o)) for o in pool if o.name not in allowed]
    case = solar_case(request.role)
    dropped: dict[str, str] = {}

    def record(found: dict[str, str], name: str) -> None:
        for outfit, why in found.items():
            dropped.setdefault(outfit, f"{why} ({name})")

    engines = [c for c in group if c.outfit.category == "Engines"]
    record(compensated_dominance(engines, corners(case, ENGINE_TRADED), ENGINE_TRADED), f"engines, {case}")
    regen = [c for c in group if c.outfit.weapon is None and any(c.attrs.get(k) for k in REGEN_KEYS)]
    record(compensated_dominance(regen, corners(case, REGEN_TRADED), REGEN_TRADED), f"regeneration, {case}")
    if request.role.goal != "capture-intact":
        forces = scored_forces(request)
        record(lens_dominance(game, group, lambda g, o: _damage_stats(g, o, forces)), "damage lens")
    record(lens_dominance(game, group, _anti_missile_stats), "anti-missile lens")
    return [o for o in pool if o.name not in dropped], dropped
