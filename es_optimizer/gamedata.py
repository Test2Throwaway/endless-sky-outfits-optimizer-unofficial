"""Load outfits, hulls and shops from Endless Sky data directories.

Follows the rules in the game's Outfit::Load, Ship::Load, Ship::FinishLoading
and Shop::Load closely enough for loadout optimization. Only top-level
definitions are read: changes applied later by events are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .datafile import Node, data_files, parse_file

# Outfit.h
DEFAULT_HYPERDRIVE_COST = 100.0
DEFAULT_SCRAM_DRIVE_COST = 150.0
DEFAULT_JUMP_DRIVE_COST = 200.0

# Attributes are stored as fixed-point integers with this many steps per unit.
ATTRIBUTE_PRECISION = 10000


def _fixed(value: float) -> float:
    return round(value * ATTRIBUTE_PRECISION) / ATTRIBUTE_PRECISION


@dataclass
class Weapon:
    # Numeric weapon stats, e.g. "reload", "shield damage", "hit force".
    stats: dict[str, float] = field(default_factory=dict)
    # Keys present with no value, e.g. "stream", "cluster", "phasing".
    flags: set[str] = field(default_factory=set)
    # Ammunition outfit consumed when firing, with the amount per shot.
    ammo: tuple[str, int] | None = None
    # Submunitions spawned by this projectile: (outfit name, count).
    submunitions: list[tuple[str, int]] = field(default_factory=list)
    # Range where damage starts and stops falling off: (start, end).
    damage_dropoff: tuple[float, float] | None = None

    def load(self, node: Node) -> None:
        for child in node:
            key = child.key
            if key == "damage dropoff" and child.size >= 2:
                self.damage_dropoff = (max(0.0, child.value(1)), child.value(2) if child.size >= 3 else 0.0)
            elif key == "ammo" and child.size >= 2:
                count = int(child.value(2)) if child.size >= 3 else 1
                self.ammo = (child.token(1), count)
            elif key == "submunition" and child.size >= 2:
                count = int(child.value(2)) if child.size >= 3 else 1
                self.submunitions.append((child.token(1), count))
            elif key == "homing":
                # Weapon::Load: a flag, optionally with a block (leading, blindspot, throttle control); the old
                # "homing <value>" form turns homing off at 0.
                if child.size == 1 or not child.is_number(1) or child.value(1) != 0:
                    self.flags.add(key)
            elif child.size == 1 and not child.children:
                self.flags.add(key)
            elif child.is_number(1):
                self.stats[key] = child.value(1)


@dataclass
class AttributeBlock:
    """What Outfit::Load reads: used for outfits and for a ship's "attributes"."""

    category: str = ""
    series: str = ""
    index: float = 0.0
    display_name: str = ""
    plural: str = ""
    cost: float = 0.0
    mass: float = 0.0
    attributes: dict[str, float] = field(default_factory=dict)
    licenses: list[str] = field(default_factory=list)
    weapon: Weapon | None = None
    ammo: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)

    def load(self, node: Node) -> None:
        for child in node:
            key = child.key
            has_value = child.size >= 2
            if key == "display name" and has_value:
                self.display_name = child.token(1)
            elif key == "category" and has_value:
                self.category = child.token(1)
            elif key == "series" and has_value:
                self.series = child.token(1)
            elif key == "index" and has_value:
                self.index = child.value(1)
            elif key == "plural" and has_value:
                self.plural = child.token(1)
            elif key == "weapon":
                if self.weapon is None:
                    self.weapon = Weapon()
                self.weapon.load(child)
            elif key == "ammo" and has_value:
                self.ammo.append(child.token(1))
            elif key == "linked" and has_value:
                self.linked.append(child.token(1))
            elif key == "description" and has_value:
                self.description.append(child.token(1))
            elif key == "cost" and has_value:
                self.cost = child.value(1)
            elif key == "mass" and has_value:
                self.mass = child.value(1)
            elif key == "licenses" and (has_value or child.children):
                for name in child.tokens[1:] + [g.key for g in child]:
                    if name not in self.licenses:
                        self.licenses.append(name)
            elif key in _IGNORED_OUTFIT_KEYS:
                continue
            elif has_value and child.is_number(1):
                self.attributes[key] = _fixed(child.value(1))

    def finish(self) -> None:
        """Defaults Outfit::Load applies after reading all keys."""
        attrs = self.attributes
        hyperdrive = attrs.get("hyperdrive", 0)
        scram = attrs.get("scram drive", 0)
        jump_drive = attrs.get("jump drive", 0)
        jump_fuel = attrs.pop("jump fuel", 0)
        if (hyperdrive or scram) and attrs.get("hyperdrive fuel", 0) <= 0:
            attrs["hyperdrive fuel"] = jump_fuel or (
                DEFAULT_SCRAM_DRIVE_COST if scram else DEFAULT_HYPERDRIVE_COST)
        if jump_drive and attrs.get("jump drive fuel", 0) <= 0:
            attrs["jump drive fuel"] = jump_fuel or DEFAULT_JUMP_DRIVE_COST
        if attrs.get("jump range", 0) < 0:
            del attrs["jump range"]


# Outfit keys that name sprites, sounds or effects rather than attributes.
_IGNORED_OUTFIT_KEYS = {
    "thumbnail", "flotsam sprite",
    "flare sprite", "reverse flare sprite", "steering flare sprite",
    "flare sound", "reverse flare sound", "steering flare sound",
    "afterburner effect", "jump effect",
    "hyperdrive sound", "hyperdrive in sound", "hyperdrive out sound",
    "jump sound", "jump in sound", "jump out sound",
    "cargo scan sound", "outfit scan sound",
}


@dataclass
class Outfit(AttributeBlock):
    name: str = ""
    source: str = ""
    deprecated: bool = False

    @property
    def label(self) -> str:
        return self.display_name or self.name


@dataclass
class Hull:
    """A ship model (variant is None) or a named variant of one."""

    name: str
    model: str
    variant: str | None = None
    display_name: str = ""
    base: AttributeBlock = field(default_factory=AttributeBlock)
    # Values from an "add attributes" node, applied on top of the base.
    added: AttributeBlock | None = None
    gun_ports: int = 0
    turret_mounts: int = 0
    bays: dict[str, int] = field(default_factory=dict)
    stock_outfits: dict[str, int] = field(default_factory=dict)
    source: str = ""
    deprecated: bool = False
    # Can't be disabled (so can't be boarded or plundered), or can't be captured. Not inherited by variants.
    never_disabled: bool = False
    uncapturable: bool = False
    # Has a sprite (own or inherited from its model). Ships without one can't be disabled, captured or plundered.
    has_sprite: bool = False
    # Loading bookkeeping, used to resolve inheritance from the model.
    _has_attributes: bool = False
    _has_outfits: bool = False
    _hardpoints: list[bool] = field(default_factory=list)  # True if it has a position
    _remove_bays: bool = False

    @property
    def category(self) -> str:
        return self.base.category

    @property
    def cost(self) -> float:
        return self.base.cost

    @property
    def mass(self) -> float:
        return self.base.mass

    @property
    def attributes(self) -> dict[str, float]:
        return self.base.attributes

    @property
    def licenses(self) -> list[str]:
        return self.base.licenses

    @property
    def label(self) -> str:
        if self.variant:
            return self.variant
        return self.display_name or self.model


@dataclass
class Shop:
    """An outfitter or shipyard: a named list of items for sale."""

    name: str
    items: list[str] = field(default_factory=list)
    # True if a "to sell" condition limits when the shop stocks its items.
    conditional: bool = False
    source: str = ""


@dataclass
class GameData:
    outfits: dict[str, Outfit] = field(default_factory=dict)
    # Ship models, keyed by model name.
    hulls: dict[str, Hull] = field(default_factory=dict)
    # Named variants, keyed by variant name.
    variants: dict[str, Hull] = field(default_factory=dict)
    outfitters: dict[str, Shop] = field(default_factory=dict)
    shipyards: dict[str, Shop] = field(default_factory=dict)
    # Named NPCs ("person" entries) and the ships they fly.
    persons: dict[str, list[str]] = field(default_factory=dict)
    # Every name used outside outfit, ship and shop definitions (missions, events, conversations, …).
    mentions: set[str] = field(default_factory=set)
    # Items added to outfitters by events (they appear in shops once the event happens).
    event_stock: set[str] = field(default_factory=set)
    # Government -> its display name (the name the player sees; several governments can share one).
    government_names: dict[str, str] = field(default_factory=dict)
    # Government -> ships (model or variant names) it flies, in fleets and mission NPCs.
    government_ships: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # Loading bookkeeping: fleet -> (government, ships); NPCs as (government, ships, fleet names).
    _fleets: dict[str, tuple[str | None, list[str]]] = field(default_factory=dict)
    _npcs: list[tuple[str, list[str], list[str]]] = field(default_factory=list)


def load(sources: list[Path] | Path) -> GameData:
    """Load game data.

    Each source is a game or plugin folder containing a "data" folder, or a data
    folder itself. Sources load in order, so later ones override earlier ones,
    matching how the game loads plugins after the base game.
    """
    if isinstance(sources, (str, Path)):
        sources = [sources]
    game = GameData()
    for source in sources:
        source = Path(source)
        data_dir = source / "data" if (source / "data").is_dir() else source
        if not data_dir.is_dir():
            raise FileNotFoundError(f"No data folder at {source}")
        for path in data_files(data_dir):
            if path.suffix != ".txt":
                continue
            label = str(path.relative_to(data_dir.parent))
            _load_nodes(game, parse_file(path, label))
    _finish(game)
    return game


def _load_nodes(game: GameData, nodes: list[Node]) -> None:
    overwrite = False
    for node in nodes:
        key = node.key
        if key == "overwrite":
            overwrite = True
            continue
        if key == "outfit" and node.size >= 2:
            name = node.token(1)
            outfit = game.outfits.get(name)
            if outfit is None or overwrite:
                outfit = game.outfits[name] = Outfit(name=name)
            _load_outfit(outfit, node)
        elif key == "ship" and node.size >= 2:
            name = node.token(2 if node.size > 2 else 1)
            table = game.variants if node.size > 2 else game.hulls
            hull = table.get(name)
            if hull is None or overwrite:
                hull = table[name] = Hull(
                    name=name, model=node.token(1),
                    variant=node.token(2) if node.size > 2 else None)
            _load_hull(hull, node)
        elif key == "person" and node.size >= 2:
            name = node.token(1)
            if overwrite or name not in game.persons:
                game.persons[name] = []
            game.persons[name] += [c.token(1) for c in node if c.key == "ship" and c.size >= 2]
        elif key == "event":
            _collect_mentions(game, node)
            for child in node:
                if child.key == "outfitter":
                    for grand in child:
                        item = grand.token(1) if grand.key == "add" and grand.size >= 2 else grand.key
                        game.event_stock.add(item)
                        for stock in (grand.children if grand.key == "stock" else []):
                            game.event_stock.add(stock.key)
        elif key in ("outfitter", "shipyard") and node.size >= 2:
            table = game.outfitters if key == "outfitter" else game.shipyards
            name = node.token(1)
            shop = table.get(name)
            if shop is None or overwrite:
                shop = table[name] = Shop(name=name)
            _load_shop(shop, node)
        elif key not in ("outfit", "ship", "outfitter", "shipyard"):
            _collect_mentions(game, node)
            if key == "government" and node.size >= 2:
                name = node.token(1)
                shown = [c.token(1) for c in node if c.key == "display name" and c.size >= 2]
                if shown or overwrite or name not in game.government_names:
                    game.government_names[name] = shown[-1] if shown else game.government_names.get(name, name)
            elif key == "fleet" and node.size >= 2:
                game._fleets[node.token(1)] = (_government_of(node), _fleet_ships(node))
            elif key == "mission":
                _load_npcs(game, node)
        overwrite = False


def _government_of(node: Node) -> str | None:
    found = [c.token(1) for c in node if c.key == "government" and c.size >= 2]
    return found[-1] if found else None


def _fleet_ships(node: Node) -> list[str]:
    """Ship names in a fleet's variants ("variant [weight]" with one ship name per child line)."""
    ships: list[str] = []
    for child in node:
        if child.key == "variant":
            ships += [c.key for c in child]
    return ships


def _load_npcs(game: GameData, mission: Node) -> None:
    stack = list(mission.children)
    while stack:
        node = stack.pop()
        if node.key != "npc":
            stack.extend(node.children)
            continue
        government = _government_of(node)
        if government is None:
            continue
        ships = [c.token(1) for c in node if c.key == "ship" and c.size >= 2]
        fleets = []
        for c in node:
            if c.key == "fleet":
                if c.size >= 2:
                    fleets.append(c.token(1))
                else:
                    ships += _fleet_ships(c)
        game._npcs.append((government, ships, fleets))


def _collect_mentions(game: GameData, node: Node) -> None:
    stack = [node]
    while stack:
        n = stack.pop()
        game.mentions.update(n.tokens)
        stack.extend(n.children)


def _load_outfit(outfit: Outfit, node: Node) -> None:
    outfit.source = outfit.source or node.where()
    outfit.deprecated = "_deprecated" in node.file
    outfit.load(node)


def _load_hull(hull: Hull, node: Node) -> None:
    hull.source = hull.source or node.where()
    hull.deprecated = "_deprecated" in node.file
    has_armament = False
    for child in node:
        key = child.key
        if key == "display name" and child.size >= 2:
            hull.display_name = child.token(1)
        elif key == "never disabled":
            hull.never_disabled = True
        elif key == "sprite" and child.size >= 2:
            hull.has_sprite = True
        elif key == "uncapturable":
            hull.uncapturable = True
        elif key == "attributes":
            hull._has_attributes = True
            hull.base.load(child)
        elif key == "add" and child.token(1) == "attributes":
            if hull.added is None:
                hull.added = AttributeBlock()
            hull.added.load(child)
        elif key in ("gun", "turret"):
            if not has_armament:
                hull._hardpoints = []
                hull.gun_ports = hull.turret_mounts = 0
                has_armament = True
            hull._hardpoints.append(child.size >= 3)
            if key == "gun":
                hull.gun_ports += 1
            else:
                hull.turret_mounts += 1
        elif key in ("fighter", "drone") and child.size >= 3:
            hull.bays[key.capitalize()] = hull.bays.get(key.capitalize(), 0) + 1
        elif key == "bay" and child.size >= 4:
            hull.bays[child.token(1)] = hull.bays.get(child.token(1), 0) + 1
        elif key == "remove" and child.token(1) == "bays":
            hull._remove_bays = True
        elif key == "outfits":
            if not hull._has_outfits:
                hull.stock_outfits = {}
                hull._has_outfits = True
            for grand in child:
                count = int(grand.value(1)) if grand.size >= 2 else 1
                if count > 0:
                    hull.stock_outfits[grand.key] = hull.stock_outfits.get(grand.key, 0) + count


def _load_shop(shop: Shop, node: Node) -> None:
    shop.source = shop.source or node.where()
    items = shop.items
    replace_stock = bool(items)
    for child in node:
        modifier = child.key in ("add", "remove")
        key = child.token(1) if modifier else child.key
        if key == "to" and child.token(2 if modifier else 1) == "sell":
            shop.conditional = child.key != "remove"
        elif key == "location":
            continue
        elif key == "stock":
            if not modifier and replace_stock:
                items.clear()
                replace_stock = False
            if child.key == "remove":
                items.clear()
            else:
                for grand in child:
                    if grand.key not in items:
                        items.append(grand.key)
        else:
            token = child.key
            if token in ("clear", "remove"):
                if child.size >= 2:
                    if child.token(1) in items:
                        items.remove(child.token(1))
                else:
                    items.clear()
            else:
                name = child.token(1) if token == "add" and child.size >= 2 else token
                if name not in items:
                    items.append(name)


def _finish(game: GameData) -> None:
    for outfit in game.outfits.values():
        outfit.finish()

    # Models first, so variants inherit fully resolved values.
    for hull in game.hulls.values():
        _finish_hull(game, hull, base=None)
    for hull in game.variants.values():
        base = game.hulls.get(hull.model)
        if base is None:
            game.warnings.append(f"{hull.source}: variant of unknown ship \"{hull.model}\"")
        _finish_hull(game, hull, base)

    for hull in list(game.hulls.values()) + list(game.variants.values()):
        for name in hull.stock_outfits:
            if name not in game.outfits:
                game.warnings.append(f"{hull.source}: \"{hull.label}\" uses undefined outfit \"{name}\"")

    flown: dict[str, set[str]] = {}
    for government, ships in game._fleets.values():
        if government:
            flown.setdefault(government, set()).update(ships)
    for government, ships, fleets in game._npcs:
        named = [s for f in fleets for s in game._fleets.get(f, (None, []))[1]]
        flown.setdefault(government, set()).update(ships + named)
    game.government_ships = {g: sorted(s) for g, s in sorted(flown.items())}
    for government in game.government_ships:
        game.government_names.setdefault(government, government)


def _finish_hull(game: GameData, hull: Hull, base: Hull | None) -> None:
    if base is not None:
        hull.has_sprite = hull.has_sprite or base.has_sprite
        if not hull.display_name:
            hull.display_name = base.display_name
        if not hull._has_attributes:
            hull.base = _copy_block(base.base)
        if not hull.bays and not hull._remove_bays:
            hull.bays = dict(base.bays)
        inherits_outfits = not hull._has_outfits
        if inherits_outfits:
            hull.stock_outfits = dict(base.stock_outfits)
        # Without positioned hardpoints, the variant uses the model's hardpoints.
        if not any(hull._hardpoints):
            hull.gun_ports = base.gun_ports
            hull.turret_mounts = base.turret_mounts
    elif hull._remove_bays:
        hull.bays = {}

    hull.base.finish()
    if hull.base.category == "Drone" and not hull.base.attributes.get("automaton"):
        hull.base.attributes["automaton"] = 1.0
    hull.base.attributes["gun ports"] = hull.gun_ports
    hull.base.attributes["turret mounts"] = hull.turret_mounts

    if hull.added is not None:
        added = hull.added
        attrs = hull.base.attributes
        for key, value in added.attributes.items():
            attrs[key] = _fixed(attrs.get(key, 0) + value)
        hull.base.cost += added.cost
        hull.base.mass += added.mass
        for name in added.licenses:
            if name not in hull.base.licenses:
                hull.base.licenses.append(name)
        hull.added = None


def _copy_block(block: AttributeBlock) -> AttributeBlock:
    return AttributeBlock(
        category=block.category, series=block.series, index=block.index,
        display_name=block.display_name, plural=block.plural,
        cost=block.cost, mass=block.mass,
        attributes=dict(block.attributes), licenses=list(block.licenses),
        weapon=block.weapon, ammo=list(block.ammo), linked=list(block.linked),
        description=list(block.description))
