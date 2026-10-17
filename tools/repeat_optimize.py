"""Run the optimizer several times on the same hull and roles, and write one file comparing the results.

The search isn't deterministic, so repeated runs show how much designs and scores vary. Runs go one after another,
each using the whole CPU (as `es-optimizer optimize` does).

    python tools/repeat_optimize.py Argosy --role warship --runs 10

Writes runs/<hull>-<roles>-<date and time>.md: a summary table (score, route, time, chosen start, metrics), a table
of which outfits each run used, and every run's full output.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from es_optimizer import calculator, cli, roles, solver  # noqa: E402
from es_optimizer.storage import Store, default_home  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("hull")
    parser.add_argument("--role", action="append", required=True, help="Role name or .toml file (up to three).")
    parser.add_argument("--runs", type=int, default=10, help="How many times to run (default 10).")
    parser.add_argument("--out", type=Path, help="Output file (default runs/<hull>-<roles>-<date and time>.md).")
    parser.add_argument("--home", type=Path, help="Tool home (default as for es-optimizer).")
    parser.add_argument("--seconds", type=float, default=2.0, help="Time limit per solver run (default 2).")
    parser.add_argument("--polish", type=float, default=60.0, help="Polish time per run (default 60).")
    parser.add_argument("--jobs", type=int, default=None, help="As for es-optimizer optimize (default: from CPUs).")
    parser.add_argument("--threads", type=int, default=None, help="As for es-optimizer optimize.")
    args = parser.parse_args(argv)

    home = args.home or default_home()
    store = Store(home)
    game, settings = store.load_catalog(), store.load_settings()
    hull = game.hulls.get(args.hull) or game.variants.get(args.hull)
    if hull is None:
        cli._not_found("hull", args.hull, list(game.hulls) + list(game.variants))
        return 1
    request = roles.combine([roles.load_role(r, home) for r in args.role], roles.shared_metrics(home), game)
    targets = None
    if request.capture_targets:
        targets = [calculator.build(game, game.hulls[n], game.hulls[n].stock_outfits) for n in request.capture_targets]

    results = []
    for run in range(1, args.runs + 1):
        start = time.monotonic()
        result = solver.optimize(game, hull, request, settings, seconds_per_solve=args.seconds,
                                 polish_seconds=args.polish, capture_targets=targets,
                                 jobs=args.jobs, threads=args.threads)
        design = result.design or result.closest
        text = io.StringIO()
        if design is not None:
            with contextlib.redirect_stdout(text):
                cli._print_design(game, design, request, result)
        results.append((result, design, text.getvalue()))
        score = f"{design.score:.3f}" if design else "—"
        print(f"run {run}/{args.runs}: {result.status}, score {score}, {time.monotonic() - start:.0f} s", flush=True)

    role_names = "+".join(Path(r).stem for r in args.role)
    out = args.out or Path("runs") / f"{hull.name}-{role_names}-{datetime.now():%Y%m%d-%H%M%S}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(hull, request, results), encoding="utf-8")
    scores = [d.score for _, d, _ in results if d is not None]
    if scores:
        print(f"scores: best {max(scores):.3f}, worst {min(scores):.3f}, mean {sum(scores) / len(scores):.3f}")
    print(f"Wrote {out}")
    return 0


def report(hull, request, results) -> str:
    lines = [f"# {hull.label} for {', '.join(r.name for r in request.roles)}: {len(results)} runs", "",
             f"{datetime.now():%Y-%m-%d %H:%M}", ""]
    metrics = request.metrics
    lines.append("| run | status | score | route | seconds | jobs × threads | chosen start | "
                 + " | ".join(metrics) + " |")
    lines.append("|" + "---|" * (7 + len(metrics)))
    for i, (result, design, _) in enumerate(results, 1):
        if design is None:
            lines.append(f"| {i} | {result.status} |" + " |" * (5 + len(metrics)))
            continue
        values = " | ".join(f"{design.metrics[m]:.4g}" for m in metrics)
        lines.append(f"| {i} | {result.status} | {design.score:.3f} | {design.route or '—'} | {result.seconds:.0f} | "
                     f"{result.jobs} × {result.threads} | {design.start} | {values} |")
    scores = [d.score for _, d, _ in results if d is not None]
    if scores:
        lines += ["", f"Score: best {max(scores):.3f}, worst {min(scores):.3f}, "
                      f"mean {sum(scores) / len(scores):.3f}"]

    used = sorted({n for _, d, _ in results if d for n in d.outfits},
                  key=lambda n: (-sum(1 for _, d, _ in results if d and n in d.outfits), n))
    lines += ["", "## Outfits per run", "",
              "| outfit | runs using it | " + " | ".join(str(i) for i in range(1, len(results) + 1)) + " |",
              "|" + "---|" * (2 + len(results))]
    for name in used:
        counts = [str(d.outfits.get(name, "")) if d else "" for _, d, _ in results]
        lines.append(f"| {name} | {sum(1 for c in counts if c)} | " + " | ".join(counts) + " |")

    for i, (result, design, text) in enumerate(results, 1):
        lines += ["", f"## Run {i}: {result.status}", "", "```", text.rstrip() or "(no design)", "```"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
