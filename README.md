# Endless Sky outfits optimizer (unofficial)

A standalone tool that designs ship loadouts for [Endless Sky](https://github.com/endless-sky/endless-sky):
given the hulls and outfits you have access to and one to three roles, it picks the outfits that best suit those roles.

Not affiliated with the Endless Sky project. It reads the game's data files and never modifies them.

## Status

- [x] Parser for the game's data files (outfits, hulls, variants, outfitters, shipyards)
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

## Tests

```sh
pip install pytest
ES_DATA=path/to/endless-sky python -m pytest
```

Without `ES_DATA`, the test against the real game data is skipped. That test checks every stock ship
in the game fits its own outfits; the only exceptions are scripted Remnant wrecks that are over capacity on purpose.
