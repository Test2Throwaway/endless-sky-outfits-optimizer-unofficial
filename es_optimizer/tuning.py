"""Tunable design numbers, overridable per run for calibration.

Each name is a module-level constant in calculator, roles or solver. `apply` sets new values; overrides also go into
the environment variable ES_OPTIMIZER_TUNING (JSON) so worker processes started later pick them up on import.
"""

from __future__ import annotations

import json
import os

ENV = "ES_OPTIMIZER_TUNING"

# name -> (module, short description)
TUNABLE = {
    "CRUISE_THRUST": ("calculator", "thrust duty cycle, replacing both of the next two (null = use them)"),
    "CRUISE_THRUST_PLAYER": ("calculator", "thrust duty cycle of player-flown ships"),
    "CRUISE_THRUST_AI": ("calculator", "thrust duty cycle of AI-flown ships (escorts)"),
    "CRUISE_TURN": ("calculator", "turn duty cycle"),
    "SECONDARY_SHARE": ("calculator", "secondary weapons' duty, replacing the stage's (null = the stage's)"),
    "PRIMARY_SHARE": ("calculator", "gun and turret duty, replacing the stage's (null = the stage's)"),
    "BATTERYLESS_SHARE": ("calculator", "share of the weapon fire generation must carry with batteries empty"),
    "BATTERYLESS_WEAPONS": ("calculator", "cheapest weapons generation must carry with batteries empty"),
    "BATTERYLESS_MANY": ("calculator", "above this many weapons, one more must be carried with batteries empty"),
    "STEER_EMPTY_COMBAT": ("calculator", "share of full turning energy left with batteries empty, in combat"),
    "STEER_EMPTY_OTHER": ("calculator", "share of full turning energy left with batteries empty, out of combat"),
    "MAGAZINE_WINDOW": ("calculator", "share of a fight long-range magazine weapons are used, by fight seconds"),
    "LONG_RANGE": ("calculator", "range above which magazine weapons only open the fight"),
    "RECOVERY_LONG": ("calculator", "recovery: the longer regeneration runs this many times its refill time"),
    "SHIELD_SELF_SUFFICIENT": ("calculator", "shields alone carry a fight if they refill within this × fight"),
    "HEAT_TARGET": ("calculator", "design heat limit (share of max heat)"),
    "COMBAT_MIN_SHOTS": ("calculator", "fire rate (shots/s) below which combat weapons lose value"),
    "COMBAT_RATE_EXPONENT": ("calculator", "how fast slow weapons lose value"),
    "TURRET_TURN_FULL": ("calculator", "turret turn (°/s) for full value"),
    "TURRET_TURN_EXPONENT": ("calculator", "how fast slow turrets lose value"),
    "PROJECTILE_SPEED_FULL": ("calculator", "projectile speed (px/s) for full value"),
    "PROJECTILE_SPEED_EXPONENT": ("calculator", "how fast slow projectiles lose value"),
    "GUN_FULL_AGILITY": ("calculator", "agility below which fixed guns lose value"),
    "COMFORT_RANGE": ("calculator", "comfortable range by agility: [[agility, range], ...]"),
    "SOLAR_COMBAT": ("calculator", "solar factor when cruising, recovering and fighting"),
    "FIGHTS": ("roles", "designed fight lengths in seconds by name"),
    "MISSILE_STRENGTH": ("calculator", "missile strength anti-missile value is measured against"),
    "TURN_ACCEL_BAND": ("calculator", "turn rate / acceleration range with no penalty: [low, high]"),
    "TURN_ACCEL_PENALTY": ("calculator", "score penalty per doubling outside the turn/acceleration band"),
    "STAGING_WIND": ("calculator", "star wind at a typical staging system (30th percentile, best within a jump)"),
    "PATIENCE": ("calculator", "seconds the player waits at staging, by mission: {routine, operation}"),
    "AM_REFERENCE_RANGE": ("calculator", "anti-missile range counted as 1x"),
    "AM_SELF_RANGE_EXPONENT": ("calculator", "how much range counts for anti-missile defending the ship itself"),
    "AM_FLEET_RANGE_EXPONENT": ("calculator", "how much range counts for fleet anti-missile (PD ships)"),
    "TAIL_SLOPE": ("solver", "score per 100% above the best stock ship"),
}


def _module(name: str):
    from . import calculator, roles, solver
    return {"calculator": calculator, "roles": roles, "solver": solver}[TUNABLE[name][0]]


def _convert(name: str, value):
    current = getattr(_module(name), name)
    if value is None:
        return None
    if isinstance(current, dict):
        # Merged into the current table: FIGHTS={"dedicated": 180} keeps the other fight lengths.
        kind = type(next(iter(current))) if current else str
        return {**current, **{kind(k): None if v is None else float(v) for k, v in dict(value).items()}}
    if isinstance(current, list):
        return [tuple(float(x) for x in item) for item in value]
    if isinstance(current, tuple):
        return tuple(float(x) for x in value)
    return float(value)


def apply(overrides: dict, export: bool = True) -> None:
    """Set tunable constants. Unknown names raise KeyError."""
    for name, value in overrides.items():
        if name not in TUNABLE:
            raise KeyError(f"Unknown tunable '{name}' (known: {', '.join(TUNABLE)})")
        setattr(_module(name), name, _convert(name, value))
    from . import calculator
    calculator._average_cache.clear()
    if export:
        merged = {**current_overrides(), **overrides}
        os.environ[ENV] = json.dumps(merged)


def current_overrides() -> dict:
    try:
        return json.loads(os.environ.get(ENV, "") or "{}")
    except ValueError:
        return {}


def parse(items: list[str]) -> dict:
    """"NAME=value" items (value as JSON, or a plain number) -> overrides."""
    out = {}
    for item in items:
        name, _, text = item.partition("=")
        try:
            out[name.strip()] = json.loads(text)
        except ValueError:
            raise KeyError(f"'{item}': give NAME=value, with value a number or JSON") from None
    return out


def snapshot() -> dict:
    """Current values of every tunable (for run records)."""
    out = {}
    for name in TUNABLE:
        value = getattr(_module(name), name)
        out[name] = {str(k): v for k, v in value.items()} if isinstance(value, dict) else value
    return out


def load_from_environment() -> None:
    overrides = current_overrides()
    if overrides:
        apply(overrides, export=False)


class override:
    """Context manager: apply overrides, restore the previous values on exit (in this process only)."""

    def __init__(self, overrides: dict):
        self.overrides = overrides

    def __enter__(self):
        import copy
        self.saved = {name: copy.deepcopy(getattr(_module(name), name)) for name in self.overrides}
        apply(self.overrides, export=False)
        return self

    def __exit__(self, *exc):
        for name, value in self.saved.items():
            setattr(_module(name), name, value)
        from . import calculator
        calculator._average_cache.clear()
        return False
