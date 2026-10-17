"""Command line for the Endless Sky outfits optimizer.

First run, import the game's data into the tool's own catalog (repeat after game updates):

    es-optimizer import path/to/endless-sky [path/to/plugin ...]

Then:

    es-optimizer summary
    es-optimizer show outfit "Heavy Laser"
    es-optimizer evaluate "Argosy (Laser)"
    es-optimizer evaluate Argosy --outfit "Heavy Laser=2" --outfit Hyperdrive
    es-optimizer block --outfit "Nerve Gas" --category Minerals
    es-optimizer unblock --outfit "Nerve Gas"
    es-optimizer blocked

Everything is available unless blocked. The catalog and settings are kept in the tool's own folder
(see --home), never in the game's files.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import calculator, gamedata
from .gamedata import GameData, Hull, Outfit
from .storage import NoCatalog, Store, catalog_to_dict, default_home


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="es-optimizer", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path,
                        help=f"Folder for the catalog and settings (default {default_home()}, "
                             "or $ES_OPTIMIZER_HOME).")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="Update the catalog from game data.")
    imp.add_argument("sources", nargs="+", type=Path,
                     help="Game or plugin folders containing data/; later ones override earlier ones.")
    sub.add_parser("summary", help="Count what is in the catalog and what is available.")
    show = sub.add_parser("show", help="Print one outfit or hull.")
    show.add_argument("kind", choices=["outfit", "hull"])
    show.add_argument("name")
    export = sub.add_parser("export", help="Write the catalog as JSON.")
    export.add_argument("output", type=Path)

    for name, help_text in (("block", "Mark outfits, hulls or categories as not available."),
                            ("unblock", "Make blocked outfits, hulls or categories available again.")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--outfit", action="append", default=[])
        p.add_argument("--hull", action="append", default=[])
        p.add_argument("--category", action="append", default=[], help="Outfit or hull category.")
        p.add_argument("--deprecated", action="store_true", help="Outfits and hulls from data/_deprecated.")
    sub.add_parser("blocked", help="List what is blocked.")

    ev = sub.add_parser("evaluate", help="Check a loadout against the design rules.")
    ev.add_argument("ship", help="A variant (uses its stock outfits) or a hull name.")
    ev.add_argument("--outfit", action="append", default=[], metavar="NAME[=COUNT]",
                    help="Outfit to install (repeatable). Replaces the stock outfits.")
    ev.add_argument("--non-combat", action="store_true")
    ev.add_argument("--fighter", action="store_true", help="Fighter or drone weapon rules.")
    ev.add_argument("--hero", action="store_true", help="Player-flown ship (no afterburner).")
    ev.add_argument("--goal", choices=sorted(calculator.DAMAGE_WEIGHTS), default="normal")
    ev.add_argument("--escort", action="store_true", help="90 s fights instead of 4 minutes.")
    ev.add_argument("--evader", action="store_true")
    ev.add_argument("--dark", action="store_true", help="Must run without solar power.")
    ev.add_argument("--long-range", action="store_true", help="Must never need to refuel at planets.")
    args = parser.parse_args(argv)

    store = Store(args.home)
    try:
        if args.command == "import":
            return _import(store, args.sources)
        game = store.load_catalog()
    except NoCatalog as error:
        print(error, file=sys.stderr)
        return 1
    settings = store.load_settings()

    if args.command == "summary":
        _summary(store, game, settings)
    elif args.command == "show":
        return _show(game, args.kind, args.name)
    elif args.command == "export":
        args.output.write_text(json.dumps(store.load_catalog_dict(), indent=1, ensure_ascii=False))
        print(f"Wrote {args.output}")
    elif args.command in ("block", "unblock"):
        return _block(store, game, settings, args, block=args.command == "block")
    elif args.command == "blocked":
        _list_blocked(game, settings)
    elif args.command == "evaluate":
        return _evaluate(game, settings, args)
    return 0


def _import(store: Store, sources: list[Path]) -> int:
    try:
        game = gamedata.load(sources)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    first = not store.has_catalog()
    changes = store.save_catalog(game, [str(s.resolve()) for s in sources])
    print(f"Imported {len(game.outfits)} outfits, {len(game.hulls)} hulls and {len(game.variants)} variants "
          f"into {store.catalog_path}")
    if game.warnings:
        print(f"{len(game.warnings)} warnings while reading the game data (see `summary`).")
    if first:
        print("Everything is available until you block it (see `block`).")
    elif changes.empty():
        print("No changes since the last import.")
    else:
        for label, group in (("New", changes.added), ("Removed", changes.removed), ("Changed", changes.changed)):
            for kind, names in group.items():
                if names:
                    shown = ", ".join(names[:10]) + (f", … ({len(names)} total)" if len(names) > 10 else "")
                    print(f"{label} {kind}: {shown}")
    unknown = store.load_settings().unknown_names(game)
    if unknown:
        print("Blocked names no longer in the game: " + ", ".join(unknown))
    return 0


def _summary(store: Store, game: GameData, settings) -> None:
    meta = store.load_catalog_dict()
    print(f"Catalog: {store.catalog_path}")
    print(f"  imported {meta['imported']} from {', '.join(meta['sources'])}")
    available_outfits = sum(settings.outfit_available(o) for o in game.outfits.values() if o.category)
    available_hulls = sum(settings.hull_available(h) for h in game.hulls.values())
    print(f"{len(game.outfits)} outfits ({available_outfits} installable and available), "
          f"{len(game.hulls)} hulls ({available_hulls} available), {len(game.variants)} variants, "
          f"{len(game.outfitters)} outfitters, {len(game.shipyards)} shipyards")
    print("\nOutfits by category:")
    for category, count in Counter(o.category or "(none)" for o in game.outfits.values()).most_common():
        print(f"  {count:4}  {category}")
    print("\nHulls by category:")
    for category, count in Counter(h.category or "(none)" for h in game.hulls.values()).most_common():
        print(f"  {count:4}  {category}")
    if game.warnings:
        print(f"\n{len(game.warnings)} warnings:")
        for warning in game.warnings:
            print("  " + warning)


def _show(game: GameData, kind: str, name: str) -> int:
    if kind == "outfit":
        item = game.outfits.get(name)
    else:
        item = game.hulls.get(name) or game.variants.get(name)
    if item is None:
        print(f"No {kind} named \"{name}\"", file=sys.stderr)
        return 1
    print(json.dumps(_item_json(item), indent=2, default=sorted, ensure_ascii=False))
    return 0


def _block(store: Store, game: GameData, settings, args, block: bool) -> int:
    categories = ({o.category for o in game.outfits.values()} | {h.category for h in game.hulls.values()}) - {""}
    unknown = ([n for n in args.outfit if n not in game.outfits]
               + [n for n in args.hull if n not in game.hulls and n not in game.variants]
               + [c for c in args.category if c not in categories])
    if unknown:
        print("Not in the catalog (names are case-sensitive): " + ", ".join(unknown), file=sys.stderr)
        return 1
    for target, names in ((settings.blocked_outfits, args.outfit), (settings.blocked_hulls, args.hull),
                          (settings.blocked_categories, args.category)):
        (target.update if block else target.difference_update)(names)
    if args.deprecated:
        settings.allow_deprecated = not block
    store.save_settings(settings)
    _list_blocked(game, settings)
    return 0


def _list_blocked(game: GameData, settings) -> None:
    rows = [("Outfits", settings.blocked_outfits), ("Hulls", settings.blocked_hulls),
            ("Categories", settings.blocked_categories)]
    if not any(names for _, names in rows):
        print("Nothing blocked by name.")
    for label, names in rows:
        if names:
            print(f"{label}: " + ", ".join(sorted(names)))
    print("Deprecated outfits and hulls: " + ("available" if settings.allow_deprecated else "blocked"))
    unknown = settings.unknown_names(game)
    if unknown:
        print("Blocked names no longer in the catalog: " + ", ".join(unknown))


def _evaluate(game: GameData, settings, args) -> int:
    hull = game.variants.get(args.ship) or game.hulls.get(args.ship)
    if hull is None:
        print(f"No ship named \"{args.ship}\"", file=sys.stderr)
        return 1
    outfits = dict(hull.stock_outfits)
    if args.outfit:
        outfits = {}
        for item in args.outfit:
            name, _, count = item.partition("=")
            outfits[name] = outfits.get(name, 0) + (int(count) if count else 1)
    role = calculator.Role(
        combat=not args.non_combat, fighter=args.fighter, hero=args.hero, goal=args.goal,
        fight_seconds=90.0 if args.escort else 240.0, evader=args.evader, must_run_dark=args.dark,
        long_range=args.long_range)
    ship = calculator.build(game, hull, outfits)
    print(f"{hull.label} ({hull.category}): mass {ship.mass:g}, cost {ship.cost:,.0f}")
    print(f"  speed {ship.max_speed:.0f}, acceleration {ship.acceleration:.0f}, turn {ship.turn_rate:.0f}, "
          f"agility {ship.agility:.0f}")
    print(f"  shields {ship.max_shields:.0f} (+{ship.shield_regen * 60:.0f}/s), "
          f"hull {ship.max_hull:.0f} (+{ship.hull_repair * 60:.0f}/s)")
    print(f"  fuel {ship.get('fuel capacity'):.0f} = {ship.jumps} jumps at {ship.average_jump_fuel:g}, "
          f"ramscoop {ship.get('ramscoop'):g}")
    for w in ship.weapons:
        print(f"  {w.count} × {w.name}: range {w.range:.0f}, "
              f"{(w.shield_damage + w.hull_damage) * 60:.0f} dmg/s, value {ship.weapon_value(w, args.goal) * 60:.0f}/s")
    blocked = [n for n in outfits if n in game.outfits and not settings.outfit_available(game.outfits[n])]
    if not settings.hull_available(hull):
        blocked.insert(0, f"hull {hull.name}")
    if blocked:
        print("  uses blocked: " + ", ".join(blocked))
    print()
    failed = 0
    for check in calculator.evaluate(ship, role):
        mark = {True: "ok  ", False: "FAIL", None: "info"}[check.passed]
        failed += check.passed is False
        print(f"  {mark}  {check.name}: {check.detail}")
    return 0 if not failed else 2


def _item_json(item: Outfit | Hull) -> dict:
    data = asdict(item)
    for key in [k for k in data if k.startswith("_")] + ["added"]:
        data.pop(key, None)
    if isinstance(item, Hull):
        data.pop("base")
        data.update(category=item.category, cost=item.cost, mass=item.mass,
                    attributes=item.attributes, licenses=item.licenses)
    return data


def to_json(game: GameData) -> dict:
    return catalog_to_dict(game, [])
