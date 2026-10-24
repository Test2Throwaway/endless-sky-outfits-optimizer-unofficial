"""The tool's own memory: its catalog of outfits and hulls, and the user's settings.

Everything lives in one per-user folder, never in the game's files:

- catalog.json: outfits, hulls, variants and shops, written by `import` from game data.
- settings.json: the blocklist (outfits and hulls not available) and other persistent choices.

The folder defaults to the platform's per-user data folder and can be moved with --home or
ES_OPTIMIZER_HOME.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .gamedata import AttributeBlock, GameData, Hull, Outfit, Shop, Weapon

CATALOG_VERSION = 5
APP_NAME = "es-optimizer"


def default_home() -> Path:
    if os.environ.get("ES_OPTIMIZER_HOME"):
        return Path(os.environ["ES_OPTIMIZER_HOME"])
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_NAME


class NoCatalog(Exception):
    pass


# --- Catalog ---

def _weapon_to_dict(w: Weapon | None) -> dict | None:
    if w is None:
        return None
    d = asdict(w)
    d["flags"] = sorted(w.flags)
    return d


def _weapon_from_dict(d: dict | None) -> Weapon | None:
    if d is None:
        return None
    return Weapon(
        stats=d["stats"], flags=set(d["flags"]),
        ammo=tuple(d["ammo"]) if d["ammo"] else None,
        submunitions=[tuple(s) for s in d["submunitions"]],
        damage_dropoff=tuple(d["damage_dropoff"]) if d["damage_dropoff"] else None)


_BLOCK_FIELDS = ["category", "series", "index", "display_name", "plural", "cost", "mass",
                 "attributes", "licenses", "ammo", "linked", "description"]


def _block_to_dict(b: AttributeBlock) -> dict:
    d = {k: getattr(b, k) for k in _BLOCK_FIELDS}
    d["weapon"] = _weapon_to_dict(b.weapon)
    return d


def _block_from_dict(d: dict, cls=AttributeBlock, **extra):
    return cls(**{k: d[k] for k in _BLOCK_FIELDS}, weapon=_weapon_from_dict(d["weapon"]), **extra)


def _outfit_to_dict(o: Outfit) -> dict:
    return {"name": o.name, "source": o.source, "deprecated": o.deprecated, **_block_to_dict(o)}


def _outfit_from_dict(d: dict) -> Outfit:
    return _block_from_dict(d, Outfit, name=d["name"], source=d["source"], deprecated=d["deprecated"])


def _hull_to_dict(h: Hull) -> dict:
    return {
        "name": h.name, "model": h.model, "variant": h.variant, "display_name": h.display_name,
        "base": _block_to_dict(h.base), "gun_ports": h.gun_ports, "turret_mounts": h.turret_mounts,
        "bays": h.bays, "stock_outfits": h.stock_outfits, "source": h.source, "deprecated": h.deprecated,
        "never_disabled": h.never_disabled, "uncapturable": h.uncapturable, "has_sprite": h.has_sprite,
    }


def _hull_from_dict(d: dict) -> Hull:
    return Hull(
        name=d["name"], model=d["model"], variant=d["variant"], display_name=d["display_name"],
        base=_block_from_dict(d["base"]), gun_ports=d["gun_ports"], turret_mounts=d["turret_mounts"],
        bays=d["bays"], stock_outfits=d["stock_outfits"], source=d["source"], deprecated=d["deprecated"],
        never_disabled=d["never_disabled"], uncapturable=d["uncapturable"], has_sprite=d["has_sprite"])


def catalog_to_dict(game: GameData, sources: list[str]) -> dict:
    return {
        "catalog version": CATALOG_VERSION,
        "imported": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": sources,
        "outfits": {k: _outfit_to_dict(v) for k, v in game.outfits.items()},
        "hulls": {k: _hull_to_dict(v) for k, v in game.hulls.items()},
        "variants": {k: _hull_to_dict(v) for k, v in game.variants.items()},
        "outfitters": {k: asdict(v) for k, v in game.outfitters.items()},
        "shipyards": {k: asdict(v) for k, v in game.shipyards.items()},
        "persons": game.persons,
        # Only names of outfits are kept: enough to tell mission items from content that is used nowhere.
        "mentions": sorted(game.mentions & set(game.outfits)),
        "event stock": sorted(game.event_stock & set(game.outfits)),
        "governments": game.government_names,
        "government ships": game.government_ships,
        "warnings": game.warnings,
    }


def catalog_from_dict(data: dict) -> GameData:
    if data.get("catalog version") != CATALOG_VERSION:
        raise NoCatalog("The catalog was written by a different version of this tool; run import again.")
    return GameData(
        outfits={k: _outfit_from_dict(v) for k, v in data["outfits"].items()},
        hulls={k: _hull_from_dict(v) for k, v in data["hulls"].items()},
        variants={k: _hull_from_dict(v) for k, v in data["variants"].items()},
        outfitters={k: Shop(**v) for k, v in data["outfitters"].items()},
        shipyards={k: Shop(**v) for k, v in data["shipyards"].items()},
        persons=data["persons"],
        mentions=set(data["mentions"]),
        event_stock=set(data["event stock"]),
        government_names=data["governments"],
        government_ships=data["government ships"],
        warnings=data["warnings"],
    )


@dataclass
class CatalogChanges:
    added: dict[str, list[str]] = field(default_factory=dict)
    removed: dict[str, list[str]] = field(default_factory=dict)
    changed: dict[str, list[str]] = field(default_factory=dict)

    def empty(self) -> bool:
        return not any(v for d in (self.added, self.removed, self.changed) for v in d.values())


def diff_catalogs(old: dict, new: dict) -> CatalogChanges:
    changes = CatalogChanges()
    for kind in ("outfits", "hulls", "variants"):
        a, b = old.get(kind, {}), new.get(kind, {})
        changes.added[kind] = sorted(set(b) - set(a))
        changes.removed[kind] = sorted(set(a) - set(b))
        changes.changed[kind] = sorted(k for k in set(a) & set(b) if _stats(a[k]) != _stats(b[k]))
    return changes


def _stats(entry: dict) -> dict:
    """The parts of a catalog entry that matter for designs (not its source location)."""
    return {k: v for k, v in entry.items() if k not in ("source",)}


class Store:
    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home else default_home()

    @property
    def catalog_path(self) -> Path:
        return self.home / "catalog.json"

    @property
    def settings_path(self) -> Path:
        return self.home / "settings.json"

    def has_catalog(self) -> bool:
        return self.catalog_path.exists()

    def load_catalog_dict(self) -> dict:
        if not self.has_catalog():
            raise NoCatalog(f"No catalog yet in {self.home}. Run: es-optimizer import path/to/endless-sky")
        return json.loads(self.catalog_path.read_text(encoding="utf-8"))

    def load_catalog(self) -> GameData:
        return catalog_from_dict(self.load_catalog_dict())

    def save_catalog(self, game: GameData, sources: list[str]) -> CatalogChanges:
        # Round-trip through JSON so tuples and lists compare equal with the stored catalog.
        new = json.loads(json.dumps(catalog_to_dict(game, sources)))
        old = self.load_catalog_dict() if self.has_catalog() else {}
        _write_json(self.catalog_path, new)
        return diff_catalogs(old, new)

    def load_settings(self) -> "Settings":
        if not self.settings_path.exists():
            return Settings()
        return Settings.from_dict(json.loads(self.settings_path.read_text(encoding="utf-8")))

    def save_settings(self, settings: "Settings") -> None:
        _write_json(self.settings_path, settings.to_dict())


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# --- Settings ---

# Source groups blocked by default: mission and test ships. Everything else is decided per government (see
# availability.default_attack, which keeps Drak, Quarg and Vyrmeid governments spared by default).
DEFAULT_BLOCKED_SOURCES = {"scripted"}

@dataclass
class Settings:
    """Persistent user choices. Everything is available unless blocked."""

    blocked_outfits: set[str] = field(default_factory=set)
    blocked_hulls: set[str] = field(default_factory=set)
    blocked_categories: set[str] = field(default_factory=set)
    # Licences the player doesn't have: outfits and hulls that need one can't be bought, but plundered outfits and
    # captured ships stay available (see availability.Availability).
    blocked_licenses: set[str] = field(default_factory=set)
    # Outfits and hulls under data/_deprecated are blocked unless this is on.
    allow_deprecated: bool = False
    # Source groups (data folders, plus "scripted") whose ships don't count as a way to get outfits.
    blocked_sources: set[str] = field(default_factory=lambda: set(DEFAULT_BLOCKED_SOURCES))
    # Explicitly allowed outfits: available even if the source rules would block them.
    allowed_outfits: set[str] = field(default_factory=set)
    # Governments the player won't attack (plundering their ships would ruin relations with them), and governments
    # the player will attack. Others follow availability.default_attack.
    blocked_governments: set[str] = field(default_factory=set)
    allowed_governments: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            "blocked outfits": sorted(self.blocked_outfits),
            "blocked hulls": sorted(self.blocked_hulls),
            "blocked categories": sorted(self.blocked_categories),
            "blocked licenses": sorted(self.blocked_licenses),
            "allow deprecated": self.allow_deprecated,
            "blocked sources": sorted(self.blocked_sources),
            "allowed outfits": sorted(self.allowed_outfits),
            "blocked governments": sorted(self.blocked_governments),
            "allowed governments": sorted(self.allowed_governments),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        return cls(
            blocked_outfits=set(d.get("blocked outfits", [])),
            blocked_hulls=set(d.get("blocked hulls", [])),
            blocked_categories=set(d.get("blocked categories", [])),
            blocked_licenses=set(d.get("blocked licenses", [])),
            allow_deprecated=d.get("allow deprecated", False),
            blocked_sources=set(d.get("blocked sources", DEFAULT_BLOCKED_SOURCES)),
            allowed_outfits=set(d.get("allowed outfits", [])),
            blocked_governments=set(d.get("blocked governments", [])),
            allowed_governments=set(d.get("allowed governments", [])),
        )

    def outfit_available(self, outfit: Outfit) -> bool:
        """Not blocked by name, category or deprecation. Licences only limit buying: see `missing_licenses`."""
        if outfit.name in self.blocked_outfits or outfit.category in self.blocked_categories:
            return False
        return self.allow_deprecated or not outfit.deprecated

    def hull_available(self, hull: Hull) -> bool:
        """Not blocked by name, category or deprecation. Licences only limit buying: see `missing_licenses`."""
        if hull.name in self.blocked_hulls or hull.category in self.blocked_categories:
            return False
        return self.allow_deprecated or not hull.deprecated

    def missing_licenses(self, item: Outfit | Hull) -> list[str]:
        """Blocked licences this outfit or hull needs to be bought."""
        return sorted(self.blocked_licenses.intersection(item.licenses))

    def unknown_names(self, game: GameData) -> list[str]:
        """Blocked names that no longer exist in the catalog (e.g. removed by a game update)."""
        return sorted((self.blocked_outfits - set(game.outfits))
                      | (self.blocked_hulls - set(game.hulls) - set(game.variants)))
