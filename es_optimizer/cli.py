"""Command line: inspect parsed game data.

    python -m es_optimizer summary --data PATH
    python -m es_optimizer show outfit "Heavy Laser" --data PATH
    python -m es_optimizer show hull "Argosy" --data PATH
    python -m es_optimizer export out.json --data PATH
    python -m es_optimizer evaluate "Argosy (Laser)" --data PATH
    python -m es_optimizer evaluate Argosy --outfit "Heavy Laser=2" --outfit Hyperdrive --data PATH
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import calculator, gamedata
from .gamedata import GameData, Hull, Outfit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="es_optimizer", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", action="append", type=Path,
                        help="Game or plugin folder (repeatable; later ones override earlier). "
                             "Defaults to $ES_DATA.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="Count what was loaded and list any warnings.")
    show = sub.add_parser("show", help="Print one outfit or hull.")
    show.add_argument("kind", choices=["outfit", "hull"])
    show.add_argument("name")
    export = sub.add_parser("export", help="Write all parsed data as JSON.")
    export.add_argument("output", type=Path)
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

    sources = args.data or ([Path(os.environ["ES_DATA"])] if os.environ.get("ES_DATA") else None)
    if not sources:
        parser.error("give --data PATH or set ES_DATA")
    game = gamedata.load(sources)

    if args.command == "summary":
        _summary(game)
    elif args.command == "show":
        return _show(game, args.kind, args.name)
    elif args.command == "evaluate":
        return _evaluate(game, args)
    elif args.command == "export":
        args.output.write_text(json.dumps(to_json(game), indent=1, default=sorted))
        print(f"Wrote {args.output}")
    return 0


def _summary(game: GameData) -> None:
    print(f"{len(game.outfits)} outfits, {len(game.hulls)} hulls, {len(game.variants)} variants, "
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
    print(json.dumps(_item_json(item), indent=2, default=sorted))
    return 0


def _evaluate(game: GameData, args) -> int:
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
    return {
        "outfits": {k: _item_json(v) for k, v in game.outfits.items()},
        "hulls": {k: _item_json(v) for k, v in game.hulls.items()},
        "variants": {k: _item_json(v) for k, v in game.variants.items()},
        "outfitters": {k: asdict(v) for k, v in game.outfitters.items()},
        "shipyards": {k: asdict(v) for k, v in game.shipyards.items()},
        "warnings": game.warnings,
    }
