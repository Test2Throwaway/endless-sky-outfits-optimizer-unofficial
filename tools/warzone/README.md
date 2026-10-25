# War-zone observation build

`tools/warzone.py` watches stock NPC fleets fight in war-zone systems, headless, to measure how the game's
own ships fight: fight length, ammo used per fight, battery drawdown, heat peaks, and when ships jump out.

It needs Endless Sky 0.11.2 with `combat-log.patch` applied, in a **separate copy** of the source:

```
git clone --branch v0.11.2 --depth 1 https://github.com/endless-sky/endless-sky es-src-0.11.2
cd es-src-0.11.2 && git apply /path/to/tools/warzone/combat-log.patch
cmake -S . -B ../es-obs-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DES_USE_VCPKG=OFF -DES_USE_SYSTEM_LIBRARIES=ON
ninja -C ../es-obs-build
```

The patch adds 108 lines and changes no behaviour. When `ES_COMBAT_LOG` names a file, the engine writes one
JSON line per ship in the player's system every 30 frames. Each line has:
- energy, heat, shields, hull and fuel, with their maximums;
- ammo per ammo outfit;
- shots per weapon since the last line;
- the distance to an enemy target;
- disabled, destroyed, jumping and fleeing flags.

Then:

```
python tools/warzone.py run --game ../es-obs-build/endless-sky --resources ../es-src-0.11.2 \
    --minutes 30 --repeats 3 --parallel 2
python tools/warzone.py analyse
```

It uses the game's integration-test mode under `xvfb-run`, which runs as fast as the CPU allows: 30 game
minutes take about 25 s on 4 cores. The player starts in a weaponless ship with no cargo space, friendly to
every government, so the NPCs only fight each other.

## How a fight is cut

A fight is **fleet against fleet**.
- **Fleet:** a leader plus every ship whose parent chain leads to it: escorts, and fighters through their
  carrier.
- **Engagement:** two fleets are engaged while a member of one targets a member of the other, and either fires
  or is within 3,000. Samples (every 0.5 s) less than 10 s apart join up, and an engagement needs at least one
  shot.
- **A fleet's fight** is the union of its engagements that overlap or come less than 10 s apart. So one fight can
  be against several fleets at once, or back to back without a breather. That's the case a player meets: usually
  1–3 fleets. Fights under 5 s are dropped.
- **Each ship's part** runs from its first sample in the fight to the fight's end, or to its first disabled or
  destroyed sample.
- **Duty:** shots × reload ÷ (the ship's time in the fight × weapons of that kind installed). It's split into
  guns, turrets (both energy weapons without ammo) and secondaries (anything using ammo). It includes time spent
  closing in, so it's the share of fight time a weapon fires, not the share of time in range. Burst weapons can
  front-load shots, so each weapon counts at most 100%.
- **Ammo per fight:** ammo used ÷ the ship's ammo when it arrived. "Fights of ammo carried" is that full load
  ÷ the ammo used, for fights that used any.
- **Retreat:** the fight ends in a jump with health below 95% (shields plus hull above the disable line, as a
  share of full). A jump at higher health counts as leaving, since NPCs also jump out to travel on.
