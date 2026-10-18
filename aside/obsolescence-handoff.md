# Handoff: plugging a "smart obsolescence" tool into the optimizer

Notes for whoever builds the obsolescence tool, so it can be merged into this repo
(`Test2Throwaway/endless-sky-outfits-optimizer-unofficial`, branch `claude/fervent-galileo-370pho`) without rework.

## Where it plugs in

`es_optimizer/solver.py`, `candidates(game, hull, settings, request) -> list[Outfit]`. It builds the pool of
outfits the search may use: available under the player's settings, allowed by the role, unique outfits only for
hero ships, and outfits needing a capacity nothing supplies removed. An obsolescence pass fits best as a function
called on that pool just before it's returned, for example:

```python
def prune_obsolete(game: GameData, hull: Hull, request: roles.Request, pool: list[Outfit]) -> tuple[list[Outfit], dict[str, str]]:
    """Kept outfits, and {dropped outfit: why (which outfit beats it)}."""
```

Returning the reasons lets the CLI print what was dropped, so the user can check it.

## Data it gets

- `Outfit` (`es_optimizer/gamedata.py`, an `AttributeBlock`): `name`, `category`, `cost`, `mass`,
  `attributes: dict[str, float]` (every other attribute, as in the game data: "outfit space" negative = uses space,
  "weapon capacity", "engine capacity", "energy generation", "heat generation", "shield generation", ...),
  `licenses`, `weapon` (a `Weapon` or None), `ammo` (ammunition names it uses), `linked`.
- `hull.attributes` (the hull's own attributes, after any "add attributes"), `hull.gun_ports`, `hull.turret_mounts`.
- `request.role`: the role being designed for, and `request.metrics` (metric names that are scored).
- `calculator.MINIMUMS`: attributes that must stay at or above a minimum (capacities); a value of None means no limit.
- Availability: `es_optimizer/availability.py`, `Availability(game, settings).outfit_reason(outfit)`, and
  `copy_limit(outfit)` (1 for unique and mission-only outfits). An outfit with a copy limit can't stand in for an
  unlimited one.

## Things that make "worse" tricky in this tool

- Everything in an outfit's attributes can matter somewhere: heat, energy per frame, thrust-made power, ramscoop,
  cooling inefficiency, cargo space, required crew, bunks. A dominance rule that ignores an attribute will drop
  outfits the scoring relies on. Unknown attributes should block pruning, not be ignored.
- Counts matter: two copies of a small outfit can beat one large one where a capacity is tight, so "A beats B per
  unit of space" is not dominance.
- Weapons are scored through `calculator.suitability` (range, fire rate, turret turn, projectile speed, magazine
  window, gun-on-slow-ship) relative to the average available weapon (`calculator.average_suitability`), so their
  value depends on the hull and the role.
- Ammunition and the launchers that use it come in pairs (`Outfit.ammo`); a launcher's value depends on its ammo
  being in the pool.
- Licences only limit buying; plundered, captured and flotsam outfits need none.

## Conventions

- Python ≥ 3.11, dependencies OR-Tools and NumPy (already installed with OR-Tools); tests in `tests/` with pytest (`python -m pytest -q`), using small
  inline game data rather than the real game files (no game data in the repo).
- Code style: 120-character lines, docstrings and comments explain why; decisions get a section in
  `docs/design-notes.md`.
