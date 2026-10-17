# Endless Sky outfits optimizer (unofficial)

A standalone tool that designs ship loadouts for [Endless Sky](https://github.com/endless-sky/endless-sky):
given the hulls and outfits you have access to and one to three roles, it picks the outfits that best suit those
roles. It aims for optimal designs, not merely workable ones, and ignores budgets.

> **Read [NOTICE.md](NOTICE.md).** This repository was generated mostly or entirely by AI. Assume it is not
> protected by copyright. Not affiliated with the Endless Sky project.

The tool keeps its own catalog of outfits and hulls and its own settings. It contains no game data: you import
the game's data once (and again after game updates), and the tool works from its catalog from then on. It never
modifies the game.

## Status

- [x] Import game data into the tool's own catalog (outfits, hulls, variants, outfitters, shipyards)
- [x] Persistent settings: everything is available unless blocked
- [x] Ship calculator: totals a loadout and checks it against the design rules in `docs/design-notes.md`
- [ ] Optimizer (one hull per run; "this hull can't do this role" is a valid result)
- [ ] Hull shortlists: optimize several hulls and rank them (TODO)
- [x] Role specs (TOML): must / should / may, 1–3 roles per design ([docs/roles.md](docs/roles.md))
- [ ] Front end (simple GUI and/or LLM)

## Usage

Requires Python 3.11+. No third-party packages are needed.

**First run:** import the game's data. Point it at the folder that contains the game's `data` folder (a game
install or a source checkout); add plugin folders after it, since later folders override earlier ones.

```sh
python -m es_optimizer import path/to/endless-sky [path/to/plugin ...]
```

Run it again after a game update; it reports which outfits and hulls were added, removed or changed.

**Availability:** everything is available unless you block it. Blocks are remembered between runs.

```sh
python -m es_optimizer block --outfit "Nerve Gas" --hull "Bactrian" --category Minerals --license "Avgi Torch"
python -m es_optimizer unblock --outfit "Nerve Gas"
python -m es_optimizer block --deprecated      # outfits and hulls from data/_deprecated (blocked by default)
python -m es_optimizer unblock --deprecated
python -m es_optimizer blocked                 # list what is blocked
```

**Inspecting and checking designs:**

```sh
python -m es_optimizer summary
python -m es_optimizer show outfit "Heavy Laser"
python -m es_optimizer show hull "Argosy"
python -m es_optimizer evaluate "Argosy (Laser)"                 # a variant uses its stock outfits
python -m es_optimizer evaluate Argosy --outfit "Heavy Laser=2" --outfit Hyperdrive --non-combat
python -m es_optimizer export catalog.json
```

**Roles** say what a ship is for (format in [docs/roles.md](docs/roles.md)):

```sh
python -m es_optimizer roles                                  # bundled and your own
python -m es_optimizer role scavenger                         # what a role asks for
python -m es_optimizer role-copy scavenger my-scavenger       # make an editable copy in your folder
python -m es_optimizer evaluate Bactrian --role scavenger --role escort
```

**Where things are stored:** `catalog.json` and `settings.json` live in a per-user folder:
`~/.local/share/es-optimizer` on Linux, `%APPDATA%\es-optimizer` on Windows,
`~/Library/Application Support/es-optimizer` on macOS. Use `--home PATH` or `ES_OPTIMIZER_HOME` to use another
folder, for example to keep separate setups.

## How the import maps to the game

The importer follows the game's own loading code, so the numbers match what the game uses:

| Here | Game source |
|---|---|
| `datafile.py` tokenizer | `DataFile::LoadData`, `DataNode::IsNumber` / `Value` |
| `AttributeBlock.load` / `finish` | `Outfit::Load` (including default jump-drive fuel) |
| `_load_hull`, `_finish_hull` | `Ship::Load`, `Ship::FinishLoading` (variant inheritance, `add attributes`, hardpoint counts) |
| `_load_shop` | `Shop::Load`, `Sale::LoadSingle` |
| file order, `overwrite` | `Files::RecursiveList`, `UniverseObjects::LoadFile` |

Notes:

- Hulls carry `gun ports` and `turret mounts` attributes counted from their hardpoints, as the game does.
  Outfits subtract from them, so a loadout fits when every capacity attribute stays at or above its minimum.
- Only top-level definitions are read. Changes applied later by in-game events are ignored.
- Outfits with no category (about 150) are mostly submunitions and other pseudo-outfits that can't be installed.

## Validation against the game

`tools/validate_with_game.py` runs the game's own data dump (`endless-sky -s --loaded`) and compares every
column with the calculator: cost, shields, hull, mass, fuel, speed, acceleration, turn, energy generation and
usage, energy capacity, idle heat, heat generation and dissipation, for every ship model with its stock outfits.
It needs a built copy of the game (built outside the game's folder; nothing in the game is modified):

```sh
python tools/validate_with_game.py path/to/endless-sky-executable path/to/endless-sky
```

Current result: all 351 ship models match on all 14 columns. The dump's speed, acceleration and turn ignore drag
reduction and multipliers, so those parts of the calculator are checked against the source code only.

## Tests

```sh
pip install pytest
ES_DATA=path/to/endless-sky python -m pytest
```

Tests that need real game data are skipped without `ES_DATA`.

## License

[Zero-Clause BSD](LICENSE), to the extent anything here is protected by copyright at all; see [NOTICE.md](NOTICE.md).
