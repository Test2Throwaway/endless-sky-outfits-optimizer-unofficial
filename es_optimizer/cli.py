"""Command line for the Endless Sky outfits optimizer.

First run, import the game's data into the tool's own catalog (repeat after game updates):

    es-optimizer import path/to/endless-sky [path/to/plugin ...]

Then:

    es-optimizer summary
    es-optimizer show outfit "Heavy Laser"
    es-optimizer evaluate "Argosy (Laser)"
    es-optimizer evaluate Argosy --outfit "Heavy Laser=2" --outfit Hyperdrive
    es-optimizer setup                      # walk through what to allow, after the first import
    es-optimizer sources                    # where outfits come from, and which sources count
    es-optimizer block --outfit "Nerve Gas" --category Minerals
    es-optimizer unblock --outfit "Nerve Gas"
    es-optimizer blocked
    es-optimizer roles
    es-optimizer evaluate "Bactrian" --role scavenger

Everything is available unless blocked. The catalog and settings are kept in the tool's own folder
(see --home), never in the game's files.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from . import calculator, gamedata, roles
from .gamedata import GameData, Hull, Outfit
from .availability import Availability
from .storage import DEFAULT_BLOCKED_SOURCES, NoCatalog, Store, catalog_to_dict, default_home


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
    hl = sub.add_parser("hulls", help="List or search hull names (available ships by default).")
    hl.add_argument("search", nargs="?", default="", help="Part of the name, any case (e.g. argo).")
    hl.add_argument("--variants", action="store_true", help="Also list named variants, e.g. \"Argosy (Laser)\".")
    hl.add_argument("--all", action="store_true", help="Also list unavailable hulls, with the reason.")
    ol = sub.add_parser("outfits", help="List or search outfit names (available outfits by default).")
    ol.add_argument("search", nargs="?", default="", help="Part of the name, any case.")
    ol.add_argument("--all", action="store_true", help="Also list unavailable outfits, with the reason.")
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
        p.add_argument("--license", action="append", default=[],
                       help="A licence you don't have: what needs it can't be bought (plundering and capturing still count).")
        p.add_argument("--deprecated", action="store_true", help="Outfits and hulls from data/_deprecated.")
        p.add_argument("--source", action="append", default=[],
                       help="Source group (data folder such as quarg, or 'scripted'): its ships stop (block) "
                            "or start (unblock) counting as a way to get outfits.")
        p.add_argument("--government", action="append", default=[],
                       help="A government (exact name, e.g. \"Korath (Civilian)\"): you won't (block) or will "
                            "(unblock) attack its ships, so they stop or start counting for plunder.")
    sub.add_parser("blocked", help="List what is blocked.")
    sub.add_parser("sources", help="List source groups and governments, and how many outfits only they supply.")
    sub.add_parser("setup", help="Walk through source groups, categories, licences and governments.")

    sub.add_parser("roles", help="List the available roles (bundled and your own).")
    rs = sub.add_parser("role", help="Show one role, with its composites expanded.")
    rs.add_argument("name")
    rc = sub.add_parser("role-copy", help="Copy a role into your own roles folder to edit it.")
    rc.add_argument("name")
    rc.add_argument("new_name", nargs="?")

    op = sub.add_parser("optimize", help="Design the best loadout for a hull and one to three roles.")
    op.add_argument("hull")
    op.add_argument("--role", action="append", required=True, help="Role name or .toml file (up to three).")
    op.add_argument("--seconds", type=float, default=2.0, help="Time limit per solver run (default 2).")
    op.add_argument("--polish", type=float, default=60.0,
                    help="Time for the final polish, shared by all starting designs (default 60).")
    op.add_argument("--target", action="append", default=[], help="Capture-intact target hull (repeatable).")
    op.add_argument("--verbose", action="store_true", help="Show each solver step.")
    op.add_argument("--emphasize", action="append", default=[],
                    help="Metric or composite to weight up for this run (repeatable), e.g. firepower: together "
                         "they take 50%% of the score; or name=share, e.g. maneuverability=0.2.")
    op.add_argument("--deprioritize", action="append", default=[],
                    help="Metric or composite to cut to 10%% of its weight for this run (repeatable), "
                         "e.g. survivability.")
    op.add_argument("--jobs", type=int, default=None,
                    help="Starting designs solved side by side in worker processes (default: from the CPU count, "
                         "two threads each; 1 = no worker processes).")
    op.add_argument("--threads", type=int, default=None, help="Solver threads per job (default: CPUs / jobs).")

    ev = sub.add_parser("evaluate", help="Check a loadout against the design rules.")
    ev.add_argument("--role", action="append", default=[],
                    help="Role name or .toml file (up to three). Replaces the flags below.")
    ev.add_argument("ship", help="A variant (uses its stock outfits) or a hull name.")
    ev.add_argument("--outfit", action="append", default=[], metavar="NAME[=COUNT]",
                    help="Outfit to install (repeatable). Replaces the stock outfits.")
    ev.add_argument("--non-combat", action="store_true")
    ev.add_argument("--fighter", action="store_true", help="Fighter or drone weapon rules.")
    ev.add_argument("--hero", action="store_true", help="Player-flown ship (no afterburner).")
    ev.add_argument("--goal", choices=calculator.GOALS, default="normal")
    ev.add_argument("--escort", action="store_true", help="90 s fights instead of 4 minutes.")
    ev.add_argument("--evader", action="store_true")
    ev.add_argument("--dark", action="store_true", help="Must run without solar power.")
    ev.add_argument("--long-range", action="store_true", help="Must never need to refuel at planets.")
    ev.add_argument("--target", action="append", default=[],
                    help="Capture-intact target hull (repeatable; default: unbuyable Pug, Korath, Heliarch, "
                         "Ka'het and Quarg warships).")
    args = parser.parse_args(argv)

    store = Store(args.home)
    try:
        if args.command == "import":
            return _import(store, args.sources)
        if args.command in ("roles", "role", "role-copy"):
            return _roles(store, args)
        game = store.load_catalog()
    except (NoCatalog, roles.RoleError) as error:
        print(error, file=sys.stderr)
        return 1
    settings = store.load_settings()

    if args.command == "summary":
        _summary(store, game, settings)
    elif args.command == "show":
        return _show(game, args.kind, args.name)
    elif args.command == "hulls":
        return _list_hulls(game, settings, args)
    elif args.command == "outfits":
        return _list_outfits(game, settings, args)
    elif args.command == "export":
        args.output.write_text(json.dumps(store.load_catalog_dict(), indent=1, ensure_ascii=False))
        print(f"Wrote {args.output}")
    elif args.command in ("block", "unblock"):
        return _block(store, game, settings, args, block=args.command == "block")
    elif args.command == "blocked":
        _list_blocked(game, settings)
    elif args.command == "sources":
        _list_sources(game, settings)
    elif args.command == "setup":
        return _setup(store, game, settings)
    elif args.command == "evaluate":
        return _evaluate(game, settings, args)
    elif args.command == "optimize":
        return _optimize(game, settings, args)
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
        print("Next: run `es-optimizer setup` to choose what counts as available. Until then: everything sold "
              "or plunderable, except sources blocked by default (" + ", ".join(sorted(DEFAULT_BLOCKED_SOURCES)) + ").")
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
    checker = Availability(game, settings)
    available_outfits = sum(checker.outfit_ok(o) for o in game.outfits.values() if o.category)
    available_hulls = sum(checker.hull_ok(h) for h in game.hulls.values())
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


def _matches(names, search: str) -> list[str]:
    search = search.lower()
    return sorted((n for n in names if search in n.lower()), key=str.lower)


def _not_found(kind: str, name: str, names) -> None:
    """Report an unknown name, with the closest names in the catalog."""
    names = list(names)
    lower = {n.lower(): n for n in names}
    close = [lower[n] for n in difflib.get_close_matches(name.lower(), list(lower), n=5, cutoff=0.6)]
    close += [n for n in _matches(names, name) if n not in close][:5]
    print(f"No {kind} named \"{name}\" (names are case-sensitive)."
          + (" Did you mean: " + ", ".join(f'"{n}"' for n in close[:8]) + "?" if close else ""), file=sys.stderr)
    print(f"List them with: es-optimizer {'outfits' if kind == 'outfit' else 'hulls'} <part of the name>",
          file=sys.stderr)


def _list_hulls(game: GameData, settings, args) -> int:
    available = Availability(game, settings)
    sold = {n for shop in game.shipyards.values() for n in shop.items}
    table = dict(game.hulls)
    if args.variants:
        table.update(game.variants)
    shown = 0
    for name in _matches(table, args.search):
        hull = table[name]
        reason = available.hull_reason(hull)
        if reason and not args.all:
            continue
        how = ("sold" if name in sold else f"variant of {hull.model}" if hull.variant
               else "capture only" if not reason else "")
        print(f"  {name:36} {hull.category:18} outfit space {hull.attributes.get('outfit space', 0):5g}  "
              f"{how}{'  [' + reason + ']' if reason else ''}")
        shown += 1
    print(f"{shown} hull(s)" + ("" if args.all else " (available; --all for every hull)")
          + ("" if args.variants else "; --variants adds named variants"))
    return 0


def _list_outfits(game: GameData, settings, args) -> int:
    available = Availability(game, settings)
    shown = 0
    for name in _matches(game.outfits, args.search):
        outfit = game.outfits[name]
        if not outfit.category:
            continue
        reason = available.outfit_reason(outfit)
        if reason and not args.all:
            continue
        print(f"  {name:40} {outfit.category:18}{'  [' + reason + ']' if reason else ''}")
        shown += 1
    print(f"{shown} outfit(s)" + ("" if args.all else " (available; --all for every outfit)"))
    return 0


def _show(game: GameData, kind: str, name: str) -> int:
    if kind == "outfit":
        item = game.outfits.get(name)
    else:
        item = game.hulls.get(name) or game.variants.get(name)
    if item is None:
        _not_found(kind, name, game.outfits if kind == "outfit" else list(game.hulls) + list(game.variants))
        return 1
    print(json.dumps(_item_json(item), indent=2, default=sorted, ensure_ascii=False))
    return 0


def _block(store: Store, game: GameData, settings, args, block: bool) -> int:
    categories = ({o.category for o in game.outfits.values()} | {h.category for h in game.hulls.values()}) - {""}
    licenses = {lic for o in game.outfits.values() for lic in o.licenses} | {
        lic for h in game.hulls.values() for lic in h.licenses}
    groups = Availability(game, settings).groups()
    unknown = ([n for n in args.government if n not in game.government_names]
               + [n for n in args.outfit if n not in game.outfits]
               + [g for g in args.source if g not in groups]
               + [n for n in args.hull if n not in game.hulls and n not in game.variants]
               + [c for c in args.category if c not in categories]
               + [lic for lic in args.license if lic not in licenses])
    if unknown:
        print("Not in the catalog (names are case-sensitive): " + ", ".join(unknown), file=sys.stderr)
        return 1
    for target, names in ((settings.blocked_outfits, args.outfit), (settings.blocked_hulls, args.hull),
                          (settings.blocked_categories, args.category),
                          (settings.blocked_licenses, args.license), (settings.blocked_sources, args.source),
                          (settings.blocked_governments, args.government)):
        (target.update if block else target.difference_update)(names)
    (settings.allowed_governments.difference_update if block else settings.allowed_governments.update)(
        args.government)
    # Naming an outfit wins over the source rules.
    (settings.allowed_outfits.difference_update if block else settings.allowed_outfits.update)(
        [n for n in args.outfit if block or Availability(game, settings).outfit_reason(game.outfits[n])])
    if args.deprecated:
        settings.allow_deprecated = not block
    store.save_settings(settings)
    _list_blocked(game, settings)
    return 0


def _list_blocked(game: GameData, settings) -> None:
    rows = [("Outfits", settings.blocked_outfits), ("Hulls", settings.blocked_hulls),
            ("Categories", settings.blocked_categories), ("Licences", settings.blocked_licenses),
            ("Sources not counted", settings.blocked_sources),
            ("Governments you won't attack", settings.blocked_governments),
            ("Governments you will attack", settings.allowed_governments),
            ("Allowed despite source rules", settings.allowed_outfits)]
    if not any(names for _, names in rows):
        print("Nothing blocked by name.")
    for label, names in rows:
        if names:
            print(f"{label}: " + ", ".join(sorted(names)))
    print("Deprecated outfits and hulls: " + ("available" if settings.allow_deprecated else "blocked"))
    unknown = settings.unknown_names(game)
    if unknown:
        print("Blocked names no longer in the catalog: " + ", ".join(unknown))


def _list_sources(game: GameData, settings) -> None:
    available = Availability(game, settings)
    print("Source groups: ships from these data folders count as a way to get their outfits (plundering, capturing, or flotsam from destroying them).")
    print("Count = outfits obtainable only from that group's ships.\n")
    for group, count in available.groups().items():
        state = "blocked" if group in settings.blocked_sources else "counted"
        print(f"  {state:8} {group:16} {count:4}")
    print("\nGovernments: plundering their ships counts if you attack them. Only governments that are a plunder")
    print("source of something you can't simply buy; counts = only from them / also from others.\n")
    for government, only, shared in available.government_choices():
        state = "attack" if available.attacks(government) else "spare"
        print(f"  {state:7} {only:4} {shared:4}  {_government_label(game, government)}")
    blocked = [o for o in game.outfits.values() if o.category and not available.outfit_ok(o)]
    print(f"\n{len(blocked)} outfits unavailable in total; `blocked` lists the settings.")


def _government_label(game: GameData, government: str) -> str:
    shown = game.government_names.get(government, government)
    return government if shown in (government, "") or not shown.strip("?") else f"{government} (shown as {shown})"


def _ask(question: str, default: bool) -> bool:
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer.startswith("y")


def _setup(store: Store, game: GameData, settings) -> int:
    """Interactive first-run setup (a stand-in for the future GUI's setup screens)."""
    print("Choose what counts as available. Press Enter to keep the suggestion.\n")
    # Source groups (data folders) are a coarse gate under the per-government choices of step 4: rarely needed.
    off = sorted(settings.blocked_sources)
    print("1. Source groups (advanced): ships from these data folders don't count at all, whatever you answer for")
    print("   their governments in step 4: " + (", ".join(off) if off else "none"))
    if _ask("   Review source groups?", False):
        for group, count in Availability(game, settings).groups().items():
            if not count:
                continue
            counted = _ask(f"   {group} ({count} outfits only from there)", group not in settings.blocked_sources)
            (settings.blocked_sources.discard if counted else settings.blocked_sources.add)(group)
    print("\n2. Outfit categories: allow outfits in this category?")
    categories = sorted({o.category for o in game.outfits.values() if o.category} - {"Licenses", "Minerals"})
    for category in categories:
        allowed = _ask(f"   {category}", category not in settings.blocked_categories)
        (settings.blocked_categories.discard if allowed else settings.blocked_categories.add)(category)
    print("\n3. Licences: do you have this licence? (Without it, what needs it can't be bought; plundered outfits"
          "\n   and captured ships still count.)")
    licenses = sorted({lic for o in game.outfits.values() for lic in o.licenses})
    for lic in licenses:
        allowed = _ask(f"   {lic}", lic not in settings.blocked_licenses)
        (settings.blocked_licenses.discard if allowed else settings.blocked_licenses.add)(lic)
    print("\n4. Governments: will you attack this government's ships to plunder them? Attacking ruins relations")
    print("   with it for good. Only governments that are a plunder source of something you can't simply buy are")
    print("   asked. Suggestions: \"(Civilian)\" governments are spared, \"(Hostile)\" ones attacked; a government")
    print("   with a \"(Civilian)\" twin is attacked, one with a \"(Hostile)\" twin is spared; others attacked.")
    available = Availability(game, settings)
    for government, only, shared in available.government_choices():
        extra = f", {shared} also from others" if shared else ""
        attack = _ask(f"   {_government_label(game, government)}: {only} outfits only from them{extra}",
                      available.attacks(government))
        (settings.allowed_governments.add if attack else settings.allowed_governments.discard)(government)
        (settings.blocked_governments.discard if attack else settings.blocked_governments.add)(government)
    settings.allow_deprecated = _ask("\n5. Allow deprecated outfits and hulls (from older saves)?",
                                     settings.allow_deprecated)
    store.save_settings(settings)
    print("\nSaved. Change any of this later with `block`, `unblock` or `setup`.")
    _list_blocked(game, settings)
    return 0


def _evaluate(game: GameData, settings, args) -> int:
    hull = game.variants.get(args.ship) or game.hulls.get(args.ship)
    if hull is None:
        _not_found("hull", args.ship, list(game.hulls) + list(game.variants))
        return 1
    outfits = dict(hull.stock_outfits)
    if args.outfit:
        outfits = {}
        for item in args.outfit:
            name, _, count = item.partition("=")
            outfits[name] = outfits.get(name, 0) + (int(count) if count else 1)
    request = None
    if args.role:
        specs = [roles.load_role(r, args.home or default_home()) for r in args.role]
        request = roles.combine(specs, roles.shared_metrics(args.home or default_home()), game)
        from . import solver
        request.role.reference_weapons = solver.reference_weapons(game, settings)
        request.role.stock_agility = solver.stock_agility(game)
        solver.resolve_percentiles(game, request)
        role = request.role
        args.goal = role.goal
        if request.capture_targets and not args.target:
            args.target = request.capture_targets
    else:
        role = calculator.Role(
            combat=not args.non_combat, fighter=args.fighter, hero=args.hero, goal=args.goal,
            fight_seconds=90.0 if args.escort else 240.0, evader=args.evader, must_run_dark=args.dark,
            long_range=args.long_range)
        from . import solver
        role.reference_weapons = solver.reference_weapons(game, settings)
        role.stock_agility = solver.stock_agility(game)
    ship = calculator.build(game, hull, outfits)
    available = Availability(game, settings)
    disruption = any(o.weapon is not None and o.weapon.stats.get("disruption damage", 0) > 0
                     and o.category and available.outfit_ok(o) for o in game.outfits.values())
    print(f"{hull.label} ({hull.category}): mass {ship.mass:g}, cost {ship.cost:,.0f}")
    print(f"  speed {ship.max_speed:.0f}, acceleration {ship.acceleration:.0f}, turn {ship.turn_rate:.0f}, "
          f"agility {ship.agility:.0f}")
    print(f"  shields {ship.max_shields:.0f} (+{ship.shield_regen * 60:.0f}/s), "
          f"hull {ship.max_hull:.0f} (+{ship.hull_repair * 60:.0f}/s)")
    print(f"  fuel {ship.get('fuel capacity'):.0f} = {ship.jumps} jumps at {ship.average_jump_fuel:g}, "
          f"ramscoop {ship.get('ramscoop'):g}")
    for w in ship.weapons:
        print(f"  {w.count} × {w.name}: range {w.range:.0f}, "
              f"{(w.shield_damage + w.hull_damage) * 60:.0f} dmg/s, "
              f"{w.shots_per_second:.3g} shots/s, "
              f"value {ship.weapon_value(w, args.goal, disruption, role.fight_seconds, role.combat, role.reference_weapons,
                                             role.stock_agility.get(hull.name)) * 60:.0f}/s")
    blocked = [f"{n} ({available.outfit_reason(game.outfits[n])})" for n in outfits
               if n in game.outfits and not available.outfit_ok(game.outfits[n])]
    if not available.hull_ok(hull):
        blocked.insert(0, f"hull {hull.name} ({available.hull_reason(hull)})")
    if blocked:
        print("  uses blocked: " + ", ".join(blocked))
    print()
    failed = 0
    targets = None
    if args.goal == "capture-intact":
        hulls = ([game.hulls.get(n) or game.variants.get(n) for n in args.target] if args.target
                 else calculator.default_capture_targets(game))
        if None in hulls:
            print("Unknown target: " + ", ".join(n for n, h in zip(args.target, hulls) if h is None), file=sys.stderr)
            return 1
        targets = [calculator.build(game, t, t.stock_outfits) for t in hulls]
    checks = calculator.evaluate(ship, role, disruption, targets)
    if request is not None:
        checks = roles.check_request(ship, request, game) + checks
    for check in checks:
        mark = {True: "ok  ", False: "FAIL", None: "info"}[check.passed]
        failed += check.passed is False
        print(f"  {mark}  {check.name}: {check.detail}")
    if request is not None:
        print("\n  should (raw values; the optimizer scores each against the stock ships):")
        for metric, weight in sorted(request.weights.items(), key=lambda kv: -kv[1]):
            parts = request.products.get(metric)
            if parts:
                print(f"    {weight:5.1%}  {metric} (product): " + ", ".join(
                    f"{m} {roles.metric_value(ship, role, m):.4g}" for m in parts))
            else:
                print(f"    {weight:5.1%}  {metric}: {roles.metric_value(ship, role, metric):.4g}")
    return 0 if not failed else 2


def _optimize(game: GameData, settings, args) -> int:
    from . import solver
    hull = game.hulls.get(args.hull) or game.variants.get(args.hull)
    if hull is None:
        _not_found("hull", args.hull, list(game.hulls) + list(game.variants))
        return 1
    home = args.home or default_home()
    request = roles.combine([roles.load_role(r, home) for r in args.role], roles.shared_metrics(home), game,
                            args.emphasize, args.deprioritize)
    targets = None
    names = args.target or request.capture_targets
    if names:
        targets = [calculator.build(game, game.hulls[n], game.hulls[n].stock_outfits) for n in names]
    result = solver.optimize(game, hull, request, settings, seconds_per_solve=args.seconds,
                             polish_seconds=args.polish, capture_targets=targets,
                             log=(lambda text: print("  · " + text, flush=True)) if args.verbose else None,
                             jobs=args.jobs, threads=args.threads)
    print(f"{hull.label} ({hull.category}) for {', '.join(r.name for r in request.roles)}: {result.status} "
          f"({result.candidates} candidate outfits, {result.iterations} solver runs, {result.seconds:.0f} s, "
          f"{result.jobs} job(s) × {result.threads} thread(s))")
    design = result.design or result.closest
    if result.status != "optimized":
        print("  This hull can't meet the role as specified. Blocked by: " + "; ".join(result.blockers))
        if design is None:
            return 2
        print("  Closest design found:")
    _print_design(game, design, request, result)
    if result.starts:
        print("\n  Starting designs (best exact score from each):")
        for label, score in result.starts:
            print(f"    {'—' if score is None else f'{score:.3f}':>6}  {label}")
        if result.design is not None:
            print(f"  Chosen: polished from \"{result.design.start}\" ({result.polish_moves} change(s))"
                  + (f"; it now scores best on {result.design.route}" if result.design.route else "") + ".")
    return 0 if result.status == "optimized" else 2


def _print_design(game: GameData, design, request, result=None) -> None:
    from . import solver
    ship = design.ship
    print(f"\n  Outfits (mass {ship.mass:g}, cost {ship.cost:,.0f}):")
    for name, count in sorted(design.outfits.items(), key=lambda kv: (game.outfits[kv[0]].category, kv[0])):
        print(f"    {count:4} × {name}  [{game.outfits[name].category}]")
    print(f"  Left: outfit space {ship.get('outfit space'):g}, weapon capacity {ship.get('weapon capacity'):g}, "
          f"engine capacity {ship.get('engine capacity'):g}")
    b = solver.balance(game, ship)
    print(f"  Balance: weapons use {b['weapon capacity used']:.0%} of weapon capacity, engines "
          f"{b['engine capacity used']:.0%} of engine capacity; outfit space: engines {b['outfit space: engines']:.0%}, "
          f"weapons {b['outfit space: weapons']:.0%}, other {b['outfit space: other']:.0%}, "
          f"free {b['outfit space: free']:.0%}")
    print(f"\n  Score {design.score:.3f}  (0.5 ≈ a typical stock ship on every weighted metric, 1 ≈ the best)"
          + (f", route: {design.route}" if design.route else ""))
    routes = request.routes or [roles.Route("", request.weights)]
    route = next((r for r in routes if r.label == design.route), routes[0])
    scales = result.scales if result else {}
    describe = lambda m: f"  ({scales[m].describe(design.metrics[m])})" if m in scales else ""
    for metric, weight in sorted(route.weights.items(), key=lambda kv: -abs(kv[1])):
        parts = request.products.get(metric)
        if parts is None:
            print(f"    {weight:+6.1%}  {metric}: {design.metrics[metric]:.4g}{describe(metric)}")
            continue
        term = solver.Scorer(request, scales).term(metric, design.metrics) if scales else None
        weights = ", ".join(f"{m} ^{w:g}" for m, w in parts.items())
        print(f"    {weight:+6.1%}  {metric}: " + (f"{term:.3f}" if term is not None else "")
              + f"  (product of scores, weights {weights})")
        for m in parts:
            print(f"              {m}: {design.metrics[m]:.4g}{describe(m)}")
    if len(routes) > 1:
        print("  Other routes: " + "; ".join(f"{r.label} {s:.3f}" for r, s in zip(routes, design.route_scores)
                                          if r is not route))
    print("\n  Checks:")
    for check in design.checks:
        mark = {True: "ok  ", False: "FAIL", None: "info"}[check.passed]
        print(f"    {mark}  {check.name}: {check.detail}")


def _roles(store: Store, args) -> int:
    if args.command == "roles":
        user_dir = store.home / "roles"
        for name, path in roles.available_roles(store.home).items():
            role = roles.load_role(str(path), store.home)
            where = "yours" if path.parent == user_dir else "bundled"
            print(f"  {name:16} {role.name}  ({where})")
        print(f"Your own roles go in {user_dir} (see `role-copy`).")
        return 0
    if args.command == "role-copy":
        source = roles.available_roles(store.home).get(args.name)
        if source is None:
            raise roles.RoleError(f"No role named '{args.name}'")
        target = store.home / "roles" / f"{args.new_name or args.name}.toml"
        if target.exists():
            print(f"{target} already exists", file=sys.stderr)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Copied to {target}; edit it there. It overrides the bundled role of the same name.")
        return 0
    role = roles.load_role(args.name, store.home)
    request = roles.combine([role], roles.shared_metrics(store.home))
    print(f"{role.name}  ({role.source})")
    if role.description:
        print("  " + role.description.strip().replace("\n", "\n  "))
    r = request.role
    kind = "fighter/drone" if r.fighter else "combat" if r.combat else "non-combat"
    flags = [kind, f"goal {r.goal}", f"{r.fight_seconds:.0f} s fights"] + [
        label for label, on in (("hero ship", r.hero), ("evader", r.evader), ("runs dark", r.must_run_dark),
                                ("long range", r.long_range), ("no ramscoop needed", not r.needs_ramscoop),
                                ("no drives needed", not r.needs_drives),
                                ("no " + ", ".join(sorted(r.excluded_drives)), bool(r.excluded_drives)),
                                ("no anti-missile needed", not r.needs_anti_missile),
                                ("no regeneration needed", not r.needs_regen)) if on]
    print("  ship: " + ", ".join(flags))
    for label, items in (("must ≥", request.must_min), ("must ≤", request.must_max)):
        for k, v in items.items():
            print(f"  {label} {k}: {v:g}")
    if request.must_have:
        print("  must have: " + ", ".join(request.must_have))
    if request.must_not:
        print("  must not have: " + ", ".join(request.must_not))
    if request.reverse_thrust:
        print(f"  must: reverse thrust {request.reverse_thrust}")
    print("  weights (should, must emphasize, may, should not; composites expanded; negative = avoid):")
    for k, v in sorted(request.weights.items(), key=lambda kv: -kv[1]):
        print(f"    {v:+6.1%}  {k}")
    if request.forbid_tags:
        print("  outfits: forbid " + ", ".join(sorted(request.forbid_tags))
              + ("; allow " + ", ".join(sorted(request.allow_tags)) if request.allow_tags else ""))
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
    return catalog_to_dict(game, [])
