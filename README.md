# Endless Sky outfits optimizer (unofficial)

A standalone tool that designs ship loadouts for [Endless Sky](https://github.com/endless-sky/endless-sky):
given the hulls and outfits you have access to and one to three roles, it picks the outfits that best suit those roles.

Not affiliated with the Endless Sky project. It reads the game's data files and never modifies them.

## Status

- [x] Parser for the game's data files (outfits, hulls, variants, outfitters, shipyards)
- [x] Ship calculator: totals a loadout and checks it against the design rules in `docs/design-notes.md`
- [ ] Optimizer
- [ ] Role specs (TOML) and command line
- [ ] Front end (simple GUI and/or LLM)

## Usage

Requires Python 3.10+. No third-party packages are needed yet.

Point the tool at an Endless Sky checkout or install (the folder containing `data/`),
either with `--data` or the `ES_DATA` environment variable:

```sh
python -m es_optimizer summary --data path/to/endless-sky
python -m es_optimizer show outfit "Heavy Laser" --data path/to/endless-sky
python -m es_optimizer show hull "Argosy" --data path/to/endless-sky
python -m es_optimizer export all.json --data path/to/endless-sky
```

Check a loadout against the design rules (a variant uses its stock outfits; `--outfit` replaces them):

```sh
python -m es_optimizer evaluate "Argosy (Laser)" --data path/to/endless-sky
python -m es_optimizer evaluate Argosy --outfit "Heavy Laser=2" --outfit Hyperdrive --non-combat --data path/to/endless-sky
```

`--data` can be repeated to load plugins after the base game; later folders override earlier ones.

From Python:

```python
import es_optimizer

game = es_optimizer.load("path/to/endless-sky")
game.outfits["Heavy Laser"].attributes   # {'outfit space': -15.0, 'weapon capacity': -15.0, 'gun ports': -1.0}
game.hulls["Argosy"].attributes["outfit space"]   # 270.0
```

## How the parser maps to the game

The parser follows the game's own loading code, so the numbers match what the game uses:

| Here | Game source |
|---|---|
| `datafile.py` tokenizer | `DataFile::LoadData`, `DataNode::IsNumber` / `Value` |
| `AttributeBlock.load` / `finish` | `Outfit::Load` (including default jump-drive fuel) |
| `_load_hull`, `_finish_hull` | `Ship::Load`, `Ship::FinishLoading` (variant inheritance, `add attributes`, hardpoint counts) |
| `_load_shop` | `Shop::Load`, `Sale::LoadSingle` |
| file order, `overwrite` | `Files::RecursiveList`, `UniverseObjects::LoadFile` |

Notes:

- Hulls carry `gun ports` and `turret mounts` attributes counted from their hardpoints, as the game does.
  Outfits subtract from them, so a loadout fits when every capacity attribute stays at or above zero.
- `cost` and `mass` are separate fields, not entries in `attributes`, matching the game.
- Only top-level definitions are read. Changes applied later by in-game events are ignored.
- Outfits with no category (about 150) are mostly submunitions and other pseudo-outfits that can't be installed.
- Definitions under `data/_deprecated` are loaded but marked `deprecated`.

## Validation against the game

`tools/validate_with_game.py` runs the game's own data dump (`endless-sky -s --loaded`) and compares every
column with the calculator: cost, shields, hull, mass, fuel, speed, acceleration, turn, energy generation and
usage, energy capacity, idle heat, heat generation and dissipation, for every ship model with its stock outfits.
It needs a built copy of the game (built outside the game's repo; nothing in the game is modified):

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

Without `ES_DATA`, the test against the real game data is skipped. That test checks every stock ship
in the game fits its own outfits; the only exceptions are scripted Remnant wrecks that are over capacity on purpose.
