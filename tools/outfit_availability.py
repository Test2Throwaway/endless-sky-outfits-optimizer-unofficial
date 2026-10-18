"""Write a Markdown list of which outfits are in play under the current settings, and why the others aren't.

    python tools/outfit_availability.py              # writes aside/outfits-in-play.md

The file lists the game's outfits, so it is not committed (see .gitignore); regenerate it after changing settings.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from es_optimizer.availability import Availability, OutfitSources  # noqa: E402
from es_optimizer.storage import Store, default_home  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--home", type=Path, help="Tool home (default as for es-optimizer).")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "aside" / "outfits-in-play.md")
    args = parser.parse_args(argv)

    store = Store(args.home or default_home())
    game, settings = store.load_catalog(), store.load_settings()
    available = Availability(game, settings)

    in_play: dict[str, list[str]] = defaultdict(list)
    out_of_play: dict[str, list[str]] = defaultdict(list)
    for name in sorted(game.outfits, key=str.lower):
        outfit = game.outfits[name]
        if not outfit.category:
            continue
        reason = available.outfit_reason(outfit)
        if reason:
            out_of_play[reason].append(f"{name} ({outfit.category})")
            continue
        src = available.sources.get(name, OutfitSources())
        if name in settings.allowed_outfits:
            how = "allowed by you"
        elif src.sold_at and not settings.missing_licenses(outfit):
            how = "sold"
        elif src.plunder:
            how = "taken from ships only (" + ", ".join(w for w in ("plunder", "capture", "flotsam") if w in src.ways) + ")"
        else:
            how = "mission or event only"
        limit = available.copy_limit(outfit)
        in_play[outfit.category].append(f"{name} — {how}" + (f", at most {limit}" if limit else ""))

    total_in = sum(map(len, in_play.values()))
    total_out = sum(map(len, out_of_play.values()))
    lines = ["# Outfits in play", "",
             f"Generated {datetime.now():%Y-%m-%d %H:%M} from the current settings: {total_in} outfits in play, "
             f"{total_out} not. Regenerate with `python tools/outfit_availability.py` after changing settings.", "",
             "## In play, by category", ""]
    for category in sorted(in_play):
        lines += [f"### {category} ({len(in_play[category])})", ""] + [f"- {e}" for e in in_play[category]] + [""]
    lines += ["## Not in play, by reason", ""]
    for reason in sorted(out_of_play, key=lambda r: -len(out_of_play[r])):
        lines += [f"### {reason[0].upper() + reason[1:]} ({len(out_of_play[reason])})", ""]
        lines += [f"- {e}" for e in out_of_play[reason]] + [""]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{total_in} in play, {total_out} not. Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
