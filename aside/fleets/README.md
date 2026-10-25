# Test fleets

Plugins that add an optimizer-designed fleet to your current save. Made by `tools/fleet_plugin.py`; the designs
behind them are in `designs/` (full optimizer output, checks included).

## Install

1. Copy the fleet folder (e.g. `late-mid/`) into `~/.local/share/endless-sky/plugins/` (for the Flatpak:
   `~/.var/app/io.github.endless_sky.endless_sky/data/endless-sky/plugins/`).
2. Start the game (the monitoring build: `tools/warzone/play.sh`) and land anywhere. An offer appears:
   "(Take the ships.)" adds the fleet, "(Not now.)" brings it back on a later landing.
3. Make the Command Starling your flagship (Player info, drag it to the top), then remove the plugin folder. The
   ships stay yours. Crew and salaries are yours from then on.

## Fleets

**late-mid/** (late mid game, Kor-style fights; your earlier settings):

| Ships | Name in game | Hull | Role |
|---|---|---|---|
| 1 | Command Starling | Starling | your flagship (your loadout) |
| 3 | KIV Warship 1–3 | Kar Ik Vot 349 | general combat |
| 2 | KIV Disabler 1–2 | Kar Ik Vot 349 | disabler |
| 4 | Beetle Disabler 1–4 | Shield Beetle | disabler |
| 2 | KIV Picket 1–2 | Kar Ik Vot 349 | point defense |

**early-mid/** (early mid game, Hai-style fights; your restricted settings, designed on your PC):

| Ships | Name in game | Hull | Role |
|---|---|---|---|
| 1 | Command Starling | Starling | your flagship (your loadout) |
| 6 | Beetle Disabler 1–6 | Shield Beetle | disabler |
| 3 | Protector Picket 1–3 | Protector | point defense |
| 3 | Falcon Warship 1–3 | Falcon | general combat |

Install one fleet at a time, ideally in its own save (copy your save first), so the two tests don't mix.
