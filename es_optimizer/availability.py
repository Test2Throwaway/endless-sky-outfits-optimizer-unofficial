"""Which outfits a player can realistically get: the blocklist plus rules based on where outfits come from.

An outfit is obtainable if it is sold in some outfitter (including stock added by events) and the player has the
licences it needs, or it is installed on a ship that can be disabled and plundered, from a source group that isn't
blocked, not flown only by governments the player won't attack (a ship no government flies has no relations to
damage, so it counts), and the outfit isn't marked unplunderable (plundered outfits need no licence). Each
government is its own choice, whatever race it belongs to; defaults come from its name (see default_attack). Outfits only mentioned in missions and similar are available but limited to one copy (given once,
often taken back later). Always blocked: unplunderable outfits sold nowhere; outfits found only on ships that
can't be disabled (person ships, never-disabled ships, ships without a sprite); outfits defined but used nowhere
(future content). Hand to Hand items, licences and minerals are never used in designs. Explicit allows and
blocks by name win over the rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .gamedata import GameData, Hull, Outfit
from .storage import Settings

# Ships that exist for missions or tests rather than as real opponents, or carry nothing worth plundering
# (the Avgi Windjammer family: minerals and a gun with a 9-hour reload). The "scripted" source group.
SCRIPTED_SHIPS = {"Rescue Dummy", "Windjammer", "Bluejacket", "Sprout"}
SCRIPTED_CATEGORIES = {"Game Mechanics"}


def source_group(hull: Hull) -> str:
    """The data folder a ship comes from (drak, quarg, korath, …), or "scripted"."""
    if hull.name in SCRIPTED_SHIPS or hull.model in SCRIPTED_SHIPS or hull.category in SCRIPTED_CATEGORIES:
        return "scripted"
    parts = hull.source.split("/")
    return parts[1] if len(parts) > 2 else "(top level)"


@dataclass
class OutfitSources:
    sold_at: list[str] = field(default_factory=list)
    # (ship name, source group, governments flying it in fleets and missions; may be none) for ships that can be
    # disabled and plundered.
    plunder: list[tuple[str, str, frozenset[str]]] = field(default_factory=list)
    # Ships it appears on that can't be plundered: person ships and ships that are never disabled.
    unplunderable_ships: list[str] = field(default_factory=list)


CIVILIAN, HOSTILE = " (Civilian)", " (Hostile)"
# Governments flying only ships from these source groups are spared by default: plundering them is unrealistic, or
# (Quarg) has large story consequences. The name rules below come first.
SPARED_SOURCES = {"drak", "quarg", "vyrmeid"}
SPARED_NAMES = {"Drak", "Quarg", "Vyrmeid"}     # also by name: "Quarg (Incipias)" flies ships defined elsewhere


def default_attack(government: str, governments, sources: set[str] = frozenset()) -> bool:
    """Whether the player attacks this government's ships unless told otherwise. "(Civilian)" governments start
    at peace and are left alone; "(Hostile)" ones are attacked; a government with a "(Civilian)" twin is the hostile
    side (Korath), one with a "(Hostile)" twin the peaceful side (Merchant). Governments whose ships all come from
    SPARED_SOURCES (`sources`: the source groups of its ships), or named after those races, are spared. Everything
    else is attacked."""
    if CIVILIAN.strip() in government:
        return False
    if HOSTILE.strip() in government:
        return True
    if government + HOSTILE in governments:
        return False
    if (sources and sources <= SPARED_SOURCES) or government.split(" (")[0] in SPARED_NAMES:
        return False
    return True


def index(game: GameData) -> dict[str, OutfitSources]:
    sources = {name: OutfitSources() for name in game.outfits}
    for shop in game.outfitters.values():
        for item in shop.items:
            if item in sources:
                sources[item].sold_at.append(shop.name)
    for item in game.event_stock:
        if item in sources and not sources[item].sold_at:
            sources[item].sold_at.append("(added by an event)")
    person_ships = {ship for ships in game.persons.values() for ship in ships}
    flown_by: dict[str, set[str]] = {}
    for government, ships in game.government_ships.items():
        for ship in ships:
            flown_by.setdefault(ship, set()).add(government)
    for hull in list(game.hulls.values()) + list(game.variants.values()):
        if hull.deprecated:
            continue
        can_plunder = not hull.never_disabled and hull.name not in person_ships and hull.has_sprite
        governments = frozenset(flown_by.get(hull.name, ()))
        group = source_group(hull)
        for name in hull.stock_outfits:
            if name not in sources:
                continue
            if can_plunder:
                sources[name].plunder.append((hull.name, group, governments))
            else:
                sources[name].unplunderable_ships.append(hull.name)
    return sources


class Availability:
    def __init__(self, game: GameData, settings: Settings):
        self.game, self.settings = game, settings
        self.sources = index(game)
        hulls = {**game.hulls, **game.variants}
        self.government_sources = {g: {source_group(hulls[s]) for s in ships if s in hulls}
                                   for g, ships in game.government_ships.items()}

    def attacks(self, government: str) -> bool:
        """The player attacks this government's ships: their own choice, else the default from its name."""
        s = self.settings
        if government in s.allowed_governments:
            return True
        if government in s.blocked_governments:
            return False
        return default_attack(government, self.game.government_names, self.government_sources.get(government, set()))

    def counts(self, group: str, governments: frozenset[str]) -> bool:
        """Plundering this ship counts: its source group is allowed, and no government flies it (no relations to
        damage) or at least one government flying it is one the player attacks."""
        return group not in self.settings.blocked_sources and (
            not governments or any(self.attacks(g) for g in governments))

    def outfit_reason(self, outfit: Outfit) -> str | None:
        """Why an outfit is not available, or None if it is."""
        s = self.settings
        if outfit.name in s.allowed_outfits:
            return None
        if not s.outfit_available(outfit):
            return "blocked"
        src = self.sources.get(outfit.name, OutfitSources())
        missing = s.missing_licenses(outfit)
        if src.sold_at and not missing:
            return None
        if not outfit.attributes.get("unplunderable"):
            if any(self.counts(group, govs) for _, group, govs in src.plunder):
                return None              # plundered: no licence needed
        if src.sold_at:
            return ("needs a licence you don't have to buy (" + ", ".join(missing)
                    + ") and can't be plundered from an allowed source")
        if outfit.attributes.get("unplunderable"):
            return "unplunderable and not sold anywhere"
        if src.plunder:
            groups = sorted({g for _, g, _ in src.plunder if g in s.blocked_sources})
            if groups and all(g in s.blocked_sources for _, g, _ in src.plunder):
                return "only on ships from blocked sources: " + ", ".join(groups)
            govs = sorted({g for _, _, gs in src.plunder for g in gs})
            return "only on ships flown by governments you won't attack: " + ", ".join(govs)
        if src.unplunderable_ships:
            return "only on ships that can't be disabled (person ships, no sprite, never disabled)"
        if outfit.name not in self.game.mentions:
            return "defined but used nowhere (future content)"
        return None          # only in missions and similar: available, one copy (see copy_limit)

    def copy_limit(self, outfit: Outfit) -> int | None:
        """At most this many copies (mission items are given once), or None for no limit."""
        if outfit.attributes.get("unique"):
            return 1
        src = self.sources.get(outfit.name, OutfitSources())
        if not src.sold_at and not src.plunder and outfit.name not in self.settings.allowed_outfits:
            return 1
        return None

    def outfit_ok(self, outfit: Outfit) -> bool:
        return self.outfit_reason(outfit) is None

    def hull_reason(self, hull: Hull) -> str | None:
        """Why a hull is not available, or None if it is. A hull needing a licence you don't have is still
        available if ships of it can be captured (they need no licence)."""
        if not self.settings.hull_available(hull):
            return "blocked"
        missing = self.settings.missing_licenses(hull)
        if not missing:
            return None
        flown = frozenset(g for g, ships in self.game.government_ships.items() if hull.name in ships)
        capturable = (not hull.uncapturable and not hull.never_disabled and hull.has_sprite
                      and self.counts(source_group(hull), flown))
        return None if capturable else (
            "needs a licence you don't have to buy (" + ", ".join(missing) + ") and can't be captured")

    def hull_ok(self, hull: Hull) -> bool:
        return self.hull_reason(hull) is None

    def government_choices(self) -> list[tuple[str, int, int]]:
        """Governments worth asking about: (government, outfits only obtainable by plundering its ships, outfits
        also plunderable elsewhere), counting only ships from allowed source groups and outfits that can't simply be
        bought. Governments that are no plunder source of anything are left out."""
        only: dict[str, int] = {}
        shared: dict[str, int] = {}
        for name, src in self.sources.items():
            outfit = self.game.outfits[name]
            if outfit.attributes.get("unplunderable") or (src.sold_at and not self.settings.missing_licenses(outfit)):
                continue
            counted = [govs for _, group, govs in src.plunder if group not in self.settings.blocked_sources]
            if any(not govs for govs in counted):
                continue                 # also on a ship no government flies: obtainable whatever you answer
            labels = {g for govs in counted for g in govs}
            tally = only if len(labels) == 1 else shared
            for label in labels:
                tally[label] = tally.get(label, 0) + 1
        chosen = [(g, only.get(g, 0), shared.get(g, 0)) for g in set(only) | set(shared)]
        return sorted(chosen, key=lambda c: (-c[1], -c[2], c[0]))

    def groups(self) -> dict[str, int]:
        """Source groups and how many outfits are obtainable only by plundering ships of that group."""
        counts: dict[str, int] = {}
        for name, src in self.sources.items():
            if src.sold_at or self.game.outfits[name].attributes.get("unplunderable"):
                continue
            groups = {g for _, g, _ in src.plunder}
            if len(groups) == 1:
                g = groups.pop()
                counts[g] = counts.get(g, 0) + 1
        for hull in list(self.game.hulls.values()) + list(self.game.variants.values()):
            counts.setdefault(source_group(hull), 0)
        return dict(sorted(counts.items()))
