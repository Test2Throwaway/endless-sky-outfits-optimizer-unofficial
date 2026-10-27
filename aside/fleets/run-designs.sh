#!/usr/bin/env bash
# Re-run the test fleets' designs on your PC. Each fleet uses its own settings, in its own folder next to your
# catalog, so your normal settings are untouched. Output: aside/fleets/designs/<fleet>/*.txt (replaces the old ones)
# and the plugin, rebuilt in aside/fleets/<fleet>/ (copy that folder into your plugins folder).
#   aside/fleets/run-designs.sh            # both fleets
#   aside/fleets/run-designs.sh late-mid   # one fleet
set -euo pipefail
cd "$(dirname "$0")/../.."
HOME_DIR=${ES_HOME:-$HOME/.local/share/es-optimizer}
CATALOG="$HOME_DIR/catalog.json"
[ -f "$CATALOG" ] || { echo "No catalog at $CATALOG: run python -m es_optimizer import <game folder> first"; exit 1; }

run_fleet() {
  local fleet=$1 stage=$2; shift 2
  local home="$HOME_DIR-$fleet"
  mkdir -p "$home" "aside/fleets/designs/$fleet"
  cp "$CATALOG" "$home/catalog.json"
  cp "aside/fleets/settings/$fleet.json" "$home/settings.json"
  for spec in "$@"; do
    IFS=: read -r hull role name <<< "$spec"
    python -m es_optimizer --home "$home" optimize "$hull" --role "$role" --stage "$stage" --seconds 4 --jobs 2 \
      > "aside/fleets/designs/$fleet/$name.txt" &
  done
  wait
  echo "$fleet: designs done"
}

D=aside/fleets/designs

if [ "${1:-late-mid}" = late-mid ] || [ -z "${1:-}" ]; then
  run_fleet late-mid late-mid "Kar Ik Vot 349:warship:kiv-warship" "Kar Ik Vot 349:disabler:kiv-disabler" \
    "Shield Beetle:disabler:beetle-disabler" "Kar Ik Vot 349:point-defense:kiv-pd"
  rm -rf aside/fleets/late-mid
  python tools/fleet_plugin.py --name "Late mid test fleet" --out aside/fleets/late-mid \
    1:"Command Starling":aside/fleets/starling-flagship.json 3:"KIV Warship":$D/late-mid/kiv-warship.txt \
    2:"KIV Disabler":$D/late-mid/kiv-disabler.txt 4:"Beetle Disabler":$D/late-mid/beetle-disabler.txt \
    2:"KIV Picket":$D/late-mid/kiv-pd.txt
fi
if [ "${1:-early-mid}" = early-mid ] || [ -z "${1:-}" ]; then
  run_fleet early-mid early-mid "Shield Beetle:disabler:beetle-disabler" "Protector:point-defense:protector-pd" \
    "Falcon:warship:falcon-warship"
  rm -rf aside/fleets/early-mid
  python tools/fleet_plugin.py --name "Early mid test fleet" --out aside/fleets/early-mid \
    1:"Command Starling":aside/fleets/starling-flagship.json 6:"Beetle Disabler":$D/early-mid/beetle-disabler.txt \
    3:"Protector Picket":$D/early-mid/protector-pd.txt 3:"Falcon Warship":$D/early-mid/falcon-warship.txt
fi
