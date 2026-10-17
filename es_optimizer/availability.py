"""Which outfits a player can realistically get: the blocklist plus rules based on where outfits come from.

An outfit is obtainable if it is sold in some outfitter (including stock added by events), or it is installed on a
ship that can be disabled and plundered, from a source group that isn't blocked, and the outfit isn't marked
unplunderable. Outfits only mentioned in missions and similar are available but limited to one copy (given once,
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
    # (ship name, source group) for ships that can be disabled and plundered.
    plunder: list[tuple[str, str]] = field(default_factory=list)
    # Ships it appears on that can't be plundered: person ships and ships that are never disabled.
    unplunderable_ships: list[str] = field(default_factory=list)


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
    for hull in list(game.hulls.values()) + list(game.variants.values()):
        if hull.deprecated:
            continue
        can_plunder = not hull.never_disabled and hull.name not in person_ships and hull.has_sprite
        group = source_group(hull)
        for name in hull.stock_outfits:
            if name not in sources:
                continue
            if can_plunder:
                sources[name].plunder.append((hull.name, group))
            else:
                sources[name].unplunderable_ships.append(hull.name)
    return sources


class Availability:
    def __init__(self, game: GameData, settings: Settings):
        self.game, self.settings = game, settings
        self.sources = index(game)

    def outfit_reason(self, outfit: Outfit) -> str | None:
        """Why an outfit is not available, or None if it is."""
        s = self.settings
        if outfit.name in s.allowed_outfits:
            return None
        if not s.outfit_available(outfit):
            return "blocked"
        src = self.sources.get(outfit.name, OutfitSources())
        if src.sold_at:
            return None
        if not outfit.attributes.get("unplunderable"):
            if any(group not in s.blocked_sources for _, group in src.plunder):
                return None
        if outfit.attributes.get("unplunderable"):
            return "unplunderable and not sold anywhere"
        if src.plunder:
            groups = sorted({g for _, g in src.plunder})
            return "only on ships from blocked sources: " + ", ".join(groups)
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

    def groups(self) -> dict[str, int]:
        """Source groups and how many outfits are obtainable only by plundering ships of that group."""
        counts: dict[str, int] = {}
        for name, src in self.sources.items():
            if src.sold_at or self.game.outfits[name].attributes.get("unplunderable"):
                continue
            groups = {g for _, g in src.plunder}
            if len(groups) == 1:
                g = groups.pop()
                counts[g] = counts.get(g, 0) + 1
        for hull in list(self.game.hulls.values()) + list(self.game.variants.values()):
            counts.setdefault(source_group(hull), 0)
        return dict(sorted(counts.items()))
