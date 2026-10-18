# Design scenarios: brainstorm for pruning and optimization

Notes from a brainstorm between the optimizer session and the obsolescence ("sheet calc") session. No code. The
first list had 13 scenarios; the user asked for about ten times that and a creative take. The workbook's sheets were
the starting point: each weapon-effect sheet (shield disabling, moving, slowing, shield disruption, tractor beam,
heat, ion, plain damage, anti-missile) and each systems sheet (jammers, scanners, fuel, drives, batteries, cooling,
shields, expansions) suggests ships built around it. Game facts were checked against the Endless Sky repo:

- damage types: shield, hull, heat, ion, scrambling, slowing, disruption, discharge, corrosion, leak, burn, energy,
  fuel, plus the "relative" variants and hit force;
- protections and resistances for most of those;
- cloak, capture attack and defense (Hand to Hand outfits), bunks, crew equivalent, gaslining, asteroid scan,
  spinal mounts, automaton;
- hull categories.

## Axes a scenario is built from

A scenario is a role archetype with a setting on each of these axes. Most of the count comes from combining them.

| Axis | Values | Closed or open |
|---|---|---|
| Archetype | the ~45 below | closed (grows slowly) |
| Engagement | burst (~30 s), escort (90 s), dedicated (240 s), siege (~600 s), none | closed |
| Light | dark (no solar), median, bright, star-hugging | closed (a few bands) |
| Enemy profile | generic; shield-heavy (Quarg, Remnant); hull-heavy; missile swarm (Syndicate, pirates); fighter/drone swarm (Kor Mereti, carriers); heat attackers (Korath Fire-Lance); ion/energy drain (Ka'het Nullifier); slowing (Inhibitor, Detainer); push/pull (Banisher, Grab-Strike, Heliarch); disruption; cloaked ambushers | closed (~10) |
| Who flies it | player flagship (hero), AI escort, AI carried fighter or drone | closed |
| Availability | early game (sold, few licences), mid game, late game (taken from ships), plus the user's government and licence choices | open per user; tiers closed |
| Money | unlimited, a credit cap | open |
| Hull band | mass and agility band; slot shape (guns vs turrets, spinal mount, bays) | continuous, but bands closed |

## Scenarios

Fields that change which outfits matter are in the right column. "Sustain" means the cruising, recovery and combat
energy and heat rules.

### 1. Likely and common

| # | Scenario | What changes which outfits matter |
|---|---|---|
| 1 | Dedicated warship, generic enemy, mid game | fight 240 s, firepower and survivability, sustain |
| 2 | Same, early game, credit cap | availability tier, cost |
| 3 | Same, late game, everything taken from ships | availability, unique outfits off |
| 4 | Escort warship, 90 s fights | fight 90 s, speed to keep up |
| 5 | Escort, early game, credit cap | cost, sold only |
| 6 | Freighter that survives being caught | cargo, survivability, combat off |
| 7 | Peaceful-area freighter | must-not jump drive and anti-missile, min cargo and jumps |
| 8 | Warship + escort | two fight lengths |
| 9 | Freighter + escort (armed trader) | cargo against weapons |
| 10 | Hero flagship warship | unique outfits, no afterburner, player skill |
| 11 | Hero flagship, all-rounder (warship + freighter + escort) | three roles balanced |
| 12 | Tank warship (durable route) | regen, pull force, low agility, gun-on-slow-ship penalty |
| 13 | Dogfighter warship (evasive route) | agility, speed, short range is fine |
| 14 | Long-range sniper | range, projectile speed, turret turn less important |
| 15 | Brawler | DPS per space, short range, heat |
| 16 | Missile boat | secondaries, ammo racks, fights per restock, magazine window |
| 17 | Point-defense escort for a fleet | anti-missile weight, turret count |
| 18 | Bounty hunter (kill one target fast) | burst engagement, alpha damage, batteries |
| 19 | Pirate hunter vs missile swarms | anti-missile, jammers (missile lock) |
| 20 | Interceptor (catch and kill small ships) | burst, speed, acceleration |
| 21 | Light warship on a small hull | slot shape, few turrets, fixed guns |
| 22 | Heavy warship on a big hull | mass band, turret-heavy |
| 23 | Medium warship upgrade of a stock ship | the stock loadout as a baseline |
| 24 | Transport (passengers) | bunks, survivability |
| 25 | Space liner | bunks, cargo, safety, no weapons focus |
| 26 | Heavy freighter in dangerous space | cargo, anti-missile, regen |
| 27 | Light freighter running cargo jobs fast | speed, jumps, cargo |
| 28 | Scavenger in battles | tractor beam, reverse thrust, push force, cargo |
| 29 | Plunder hauler that disables and boards | goal disable, cargo, shield-heavy weapons |
| 30 | Capture specialist (boarding) | goal disable, capture attack/defense (Hand to Hand), bunks, crew |
| 31 | Explorer (long trips, refuel anywhere) | long range, ramscoop, fuel, jump drive |
| 32 | Explorer in dark regions | solar off, generators and batteries, fuel |
| 33 | Solar-powered cheap ship (bright regions) | solar collectors, heat at bright stars |
| 34 | Missions with fixed cargo and passengers | min cargo and bunks |
| 35 | Fleet line ship (AI-flown) | no hero-only outfits, simple weapons |
| 36 | Warship vs heat attackers (Korath) | heat protection, cooling headroom |
| 37 | Warship vs ion attackers (Ka'het) | ion protection and resistance, energy storage |
| 38 | Warship vs shield-heavy targets (Quarg, Remnant) | shield-disabling and disruption weapons |
| 39 | Warship vs hull-heavy targets | hull damage weights |
| 40 | Warship vs fighter swarms | flak, turrets, fire rate, anti-missile-style coverage |

### 2. Likely but uncommon

| # | Scenario | What changes which outfits matter |
|---|---|---|
| 41 | Heat-death striker (overheat targets) | heat damage, its own cooling to sustain |
| 42 | Ion drainer | ion and energy damage, scrambling |
| 43 | Slowing harasser (cripple engines, kite) | slowing damage, range, agility |
| 44 | Disruptor + hull combo | disruption plus hull-damage pair |
| 45 | Shield stripper for capture | shield-disabling weapons, low hull damage |
| 46 | Push wall (keep enemies at bay) | hit force, Banisher/Expeller |
| 47 | Puller tank (drag enemies in) | Grab-Strike, pull force |
| 48 | Gravity anchor for a fleet | pull and push combined, durable |
| 49 | Tractor salvager (flotsam farming) | tractor beam range and count, cargo |
| 50 | Flotsam farmer of a specific drop (Antimatter Power Cell) | kill speed against that ship, tractor, cargo |
| 51 | Asteroid miner | asteroid scan, minable damage, cargo |
| 52 | Smuggler | cargo and outfit scan opacity, jammers, speed |
| 53 | Blockade runner | speed, jammers, survivability, burst escape |
| 54 | Scout / scanner | tactical, cargo and outfit scanners, speed |
| 55 | Electronic-warfare escort | jammers, scan interference |
| 56 | Cloaked ambusher | cloak, cloaked attributes, alpha damage |
| 57 | Cloaked transport | cloak, cargo |
| 58 | Carrier (launches fighters/drones) | bays, its own defence, support outfits |
| 59 | Fighter carried by a carrier | fighter weapon rules, tiny slots, no drives |
| 60 | Drone | drone rules, automaton, no crew |
| 61 | Escort-carrier hybrid | bays, 90 s fights |
| 62 | Siege ship (long engagements) | ~600 s sustain, regen, deep magazines |
| 63 | Alpha striker (first 10 s matter) | burst, batteries, heat buffer |
| 64 | Hit-and-run raider | burst, speed, retreat |
| 65 | Pirate raider (disable traders, loot) | goal disable, cargo, speed |
| 66 | Anti-pirate convoy guard | anti-missile, 90 s, regen |
| 67 | Fleet repair and recovery tender | hull repair, fuel, AI behaviours |
| 68 | Fuel tanker for a fleet | fuel capacity, ramscoop |
| 69 | Long-range gunboat on a slow hull | the gun penalty against turrets, range |
| 70 | Beam boat (instantaneous only) | instantaneous weapons, energy |
| 71 | Ammo-free ship (no restocking) | no secondaries, energy weapons only |
| 72 | Missile-only ship | secondaries only, ammo depth |
| 73 | Mixed primaries + secondaries | the 80% secondary window |
| 74 | Cheap disposable escort | credit cap, cost per value |
| 75 | Max value for money | value per credit |
| 76 | Stealth-free flagship (max raw power) | unique outfits, late game |
| 77 | Spinal-mount warship | spinal mount weapons |
| 78 | Star-hugger (fight at bright stars) | solar heat, solar power, heat |
| 79 | Dark-transit warship | no solar, battery buffer |
| 80 | Gas-giant lander | gaslining |
| 81 | Korath-territory explorer | heat protection, long range |
| 82 | Remnant-space operator | slowing resistance, cloak awareness |
| 83 | Hai-space trader | jammers (Hai), cargo |
| 84 | Wanderer-tech warship | Wanderer outfits, regen |
| 85 | Coalition/Heliarch-tech ship | push/pull, licences |
| 86 | Pug-tech defender | Pug outfits, anti-missile |
| 87 | Quarg-hunting (if the user allows it) | anti-shield, huge targets |
| 88 | Human-tech purist (only human outfits) | availability by source group |
| 89 | Alien-tech showcase (only one race's tech) | source-group filters |
| 90 | Restock-limited (3+ fights per restock) | fights per restock, ammo |

### 3. Unlikely and uncommon

| # | Scenario | What changes which outfits matter |
|---|---|---|
| 91 | Capture-intact of a specific hull | instantaneous only, target list |
| 92 | Capture-intact of a big target | capture attack, shield-only damage |
| 93 | Must run dark (no solar, no heat signature) | heat, cloaking, solar off |
| 94 | Fighter interceptor (fighter vs fighters) | fighter rules, fire rate |
| 95 | Interceptor-drone swarm member | drone, tiny slots |
| 96 | Destroy-only ship (no loot interest) | goal destroy, hull damage |
| 97 | Corrosion or leak damage specialist | corrosion and leak damage |
| 98 | Discharge damage specialist | discharge damage |
| 99 | Burn damage specialist | burn damage, heat |
| 100 | Fuel-drain raider (strand targets) | fuel and leak damage |
| 101 | Scrambler (make targets miss) | scrambling damage |
| 102 | Anti-cloak hunter | scanners, tactical scan |
| 103 | Mine layer | Korath mines, area denial |
| 104 | Torpedo bomber vs capital ships | heavy secondaries, alpha |
| 105 | Self-destruct decoy | self destruct, cheap |
| 106 | Decoy tank (draws fire) | Decoy Plating, durability |
| 107 | Holovid / Phantom Pallet trickster | jammers, scan opacity |
| 108 | Research vessel | Research Laboratory, scanners |
| 109 | Asteroid scanner prospector | asteroid scan power |
| 110 | Max cargo, no weapons at all | must-not weapons |
| 111 | Max speed courier | speed, jumps, nothing else |
| 112 | Max jump range | jump fuel, fuel capacity |
| 113 | Max bunks (crew for captures) | bunks, capture |
| 114 | Max regen fortress (immobile) | regen, no agility floor |
| 115 | Max agility (no weapons) | agility only |
| 116 | Minimum-mass ship | mass |
| 117 | Minimum-heat ship | heat generation |
| 118 | Minimum energy use | energy draw |
| 119 | Zero-crew automaton ship | automaton, crew |
| 120 | Escort for a specific mission fleet (keep up with a slow hull) | speed matched to a target |
| 121 | Specific-enemy counter-build (named government's ships) | enemy profile from actual hulls |
| 122 | Arena duel vs one named hull | targets list, burst |
| 123 | Siege vs a station or planet defence | long fights, range |
| 124 | Very early game (starting credits, first ship) | tiny credit cap, sold only |
| 125 | Licence-limited (no navy licences) | licences |
| 126 | Government-limited (refuses to fight Hai) | governments |
| 127 | Source-limited (no Korath tech) | source groups |
| 128 | Speedrun: best design reachable before a story point | event-gated stock |
| 129 | Superheavy hulls (excluded today) | huge mass band |
| 130 | Unique-only stress test (every unique allowed) | uniques, copy limits |
| 131 | Fleet composition (several hulls designed together) | cross-ship roles: one tank, one PD, one sniper |
| 132 | Carrier + its own fighters designed together | bays plus fighter designs |
| 133 | Same role across a shortlist of hulls (pick the best hull) | hull bands, many runs |
| 134 | Refit: change as few outfits as possible from the current loadout | the current loadout as a baseline, change cost |
| 135 | Upgrade path: the next affordable step from the current loadout | credit cap, current loadout |

## What this means for the pruner (sheet calc)

1. **Shapes multiply, so don't pre-run kept lists.** About 45 archetypes × 5 engagements × 4 light bands × 10 enemy
   profiles × 3 pilots × 3 availability tiers × several hull bands is tens of thousands of shapes. Store dominance
   *relations* instead: "A is beaten by B (or by a set), valid over this region of the lens axes." Do it once per
   game update. Applying them to a request is then cheap set work.
2. **The value vector is much wider than "true cost".** Each workbook effect sheet is its own value axis:
   - damage: shield, hull, heat, ion, scrambling, slowing, disruption, discharge, corrosion, leak, burn, energy,
     fuel, and push or pull force;
   - defence: protections and resistances;
   - systems: jamming, scan opacity, scanning, cloak, capture attack and defense, bunks, crew equivalent, gaslining,
     asteroid scan, tractor.

   Dominance has to hold on every axis that any lens in the region values. A weapon with a unique effect is never
   dominated by a plain damage weapon.
3. **Enemy profiles are lenses.** An enemy profile reweights the damage axes (heat is worthless against heat-immune
   targets, ion is strong against energy-starved ones) and the protection axes. Grouping weapons by effect, as the
   workbook does, matches this.
4. **Keep the front, not one winner.** The kept set per family is a Pareto front over the lens region. Report its
   size; a front of 1 is a warning sign.
5. **Hull facts as bands, not numbers.** Agility band (gun-on-slow-ship penalty, comfortable range, thrust-made
   power), mass band (heat capacity), slot shape (gun ports against turret mounts, spinal mount, bays).
6. **Money is a lens.** Under a credit cap, a cheap outfit that's worse on everything else isn't dominated by an
   expensive one. "Value per credit" scenarios need cost as a cost axis.
7. **Pairs and limits.**
   - Launchers come with their ammo; ammo depth depends on fights per restock.
   - Copy-limited outfits (unique, mission-only) can't replace several copies of another.
   - Counts: two small outfits against one large one.
8. **Output contract.** For each dropped outfit: what beats it, over which region, and from which availability tier
   the replacement comes. The optimizer then checks that the replacement is available to this user.

## What this means for the optimizer (this repo)

1. **Request → shape key.** The optimizer has to map a request onto the pruner's closed axes: archetype, engagement,
   light band, enemy profile, pilot, availability tier, hull band. The open-ended parts (weights, minimums, tags,
   budgets) narrow at run time and never prune.
2. **Missing request fields and features.** Most of the 135 scenarios need something the optimizer doesn't have yet:
   - a credit cap and cost-aware scoring (scenarios 2, 5, 74, 75, 124, 135);
   - enemy profiles that set damage-type weights and require protections (36–40, 121);
   - scoring for effect damage (heat, ion, slowing, disruption, scrambling, discharge, corrosion, leak, burn). Today
     weapon value counts shield and hull damage, weighted by goal;
   - Hand to Hand outfits (capture attack and defense) for boarding and capture roles. They are excluded from the
     pool today (`NOT_INSTALLABLE`), which is wrong for scenarios 29, 30, 91, 92 and 113;
   - bunks and passengers, mining, smuggling (scan opacity), scanning, cloak, gaslining;
   - light as a request field (dark-region and star-hugging ships). Today solar is fixed at ×0.49 and ×2.09;
   - more engagement lengths: burst (~30 s) and siege (~600 s), as well as 90 and 240 s;
   - pilot: AI-flown escorts against the player's flagship;
   - carriers and their fighters, and fleets designed together;
   - refit and upgrade-path modes: the cost of changing from a current loadout.
3. **New roles are mostly TOML.** Many archetypes are role files plus a few new metrics: heat-death striker, ion
   drainer, slowing harasser, point-defense escort, smuggler, scout, miner, tractor salvager, missile boat, siege
   ship, alpha striker. Effect-damage metrics and enemy profiles are the main code work.
4. **Safety net.** The polish stage re-tries the best dropped outfits and reports any that would have improved the
   design. CLI: "pruned N of M (power X, weapons Y, …)", a flag to list the pruned outfits with what beats them, and
   `--no-prune`.
5. **Speed.** A smaller pool means more starting points in the same time. Per-hull shortlists (scenario 133) and
   fleets (131) multiply runs, so pruning matters most there.
6. **Keep the weapon reference set independent of pruning.** The average weapon used by weapon value comes from
   availability, not from the candidate pool. Pruning must not change it.
