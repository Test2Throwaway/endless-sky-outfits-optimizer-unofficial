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
    "CRUISE_THRUST": ("calculator", "thrust duty cycle out of combat and in combat"),
    "CRUISE_TURN": ("calculator", "turn duty cycle"),
    "SECONDARY_SHARE": ("calculator", "secondary weapons' duty during their window"),
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
    "TAIL_SLOPE": ("solver", "score per 100% above the best stock ship"),
}


def _module(name: str):
    from . import calculator, roles, solver
    return {"calculator": calculator, "roles": roles, "solver": solver}[TUNABLE[name][0]]


def _convert(name: str, value):
    current = getattr(_module(name), name)
    if isinstance(current, dict):
        return {type(next(iter(current))) (k) if current else k: float(v) for k, v in dict(value).items()}
    if isinstance(current, list):
        return [tuple(float(x) for x in item) for item in value]
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
