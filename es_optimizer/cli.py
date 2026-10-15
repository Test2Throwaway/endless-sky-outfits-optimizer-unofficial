"""Command line: inspect parsed game data.

    python -m es_optimizer summary --data PATH
    python -m es_optimizer show outfit "Heavy Laser" --data PATH
    python -m es_optimizer show hull "Argosy" --data PATH
    python -m es_optimizer export out.json --data PATH
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import gamedata
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
    args = parser.parse_args(argv)

    sources = args.data or ([Path(os.environ["ES_DATA"])] if os.environ.get("ES_DATA") else None)
    if not sources:
        parser.error("give --data PATH or set ES_DATA")
    game = gamedata.load(sources)

    if args.command == "summary":
        _summary(game)
    elif args.command == "show":
        return _show(game, args.kind, args.name)
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
