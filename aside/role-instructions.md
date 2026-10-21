# Optimizer instructions for the brainstormed ship roles

Every scenario from the combined brainstorm (the sheet-calc session's `docs/scenario-brainstorm.md`, draft 3),
written as instructions in the user's framework: **ship** settings, then **should**, **must**, **must not**,
**should not**, **may**. The aim is to find out which levers the tool needs. Levers it doesn't have yet are expected
and are marked **NEW**. Weights are placeholders that show emphasis (3 = main goal, 1 = minor). They are not tuned.

Numbers match the brainstorm. Its unnumbered "added from the optimizer session" items are numbered A1–A45 here.

## How to read an entry

```
#  Name — tier
ship: …      [ship] settings (combat, fight length, goal, hero, …)
should: …    weighted metrics to maximise
must: …      hard requirements (min values, must-have stats, percentile floors)
must not: …  hard exclusions
should not: … negative weights
may: …       small bonuses
levers: …    levers the entry uses that don't exist yet (NEW), and anything unusual
```

Sections an entry doesn't need are left out. Defaults that always apply unless switched off: drives (hyperdrive,
jump drive, quantum keystone), ramscoop, anti-missile, some regeneration, the cruising and recovery sustain rules,
and the fit rule.

## Lever catalogue

### Existing

- **Ship flags:** combat, fighter, hero (no afterburner, uniques), evader, must_run_dark, long_range,
  needs_ramscoop / needs_drives / needs_anti_missile / needs_regen, fights_per_restock, capture_targets,
  weapons_budget / engines_budget, unique_outfits.
- **Fight lengths:** escort (90 s), dedicated (240 s).
- **Goals:** normal, disable, capture-intact, destroy.
- **Metrics:** max speed, acceleration, reverse acceleration, turn rate, agility, effective shields/hull, shield regen,
  hull repair, weapon value, shield/hull DPS, anti-missile, tractor beam, push/pull force, jumps, free outfit space.
  Also any outfit or hull attribute summed over the ship (bunks, cargo space, radar jamming, cargo scan opacity,
  asteroid scan power, ion protection, …).
- **Composites:** survivability (best of durable/evasive), maneuverability (turn × acceleration), speed, firepower.
- **Sections and modifiers:** should / must (min, has, min_percentile, reverse_thrust level) / must not / should not /
  may (bonus); emphasize / deprioritize.
- **Outfit tags (forbid/allow):** damage weapon, anti-missile, tractor beam, push weapon, pull weapon, instantaneous,
  shield disruption, missile, fuel weapon, afterburner, cloak, illegal, solar, ramscoop, torch.
- **Availability settings (global, not per request):** licences, governments, source groups, blocked/allowed outfits.

### New levers this list asks for

| ID | Lever | What it is |
|---|---|---|
| N1 | **cost** | Credit cap (must), cost as a metric to minimise (should not), value per credit |
| N2 | **running cost** | Crew salaries and operating costs per day |
| N3 | **resale value** | Depreciation-aware cost |
| N4 | **installed** | Keep the current loadout; cap the number of changes; vary only one family (weapons, engines, …) |
| N5 | **effect damage** | Metrics for heat, ion, scrambling, slowing, disruption, discharge, corrosion, leak, burn, energy and fuel damage per second; relative (percentage) damage |
| N6 | **enemy profile** | Who the ship fights: damage-type weights, the shield-to-hull ratio of targets, the protections needed against their weapons, their speed and range. Generic presets (shield-heavy, missile swarm, Korath, Ka'het, …) or built from a named government's or hull's data |
| N7 | **fight shape** | Burst (~30 s), siege (~600 s) or any length in seconds; a chain of waves with recovery gaps between them |
| N8 | **start state** | Combat starting hot (at cruising-plus heat) or at a bright star |
| N9 | **light** | Solar case per request: dark, dim, median, bright, star-hugging; solar wind |
| N10 | **availability mode** | Per request: sold only, taken from ships only, one faction or source only, before a story event |
| N11 | **capture strength** | Crew × capture attack and defense (Hand to Hand outfits in the pool), boarding crew in bunks, capture odds against a target |
| N12 | **bays** | Carriers: bay counts by type, the carried craft, repair of carried craft |
| N13 | **fleet** | Design several ships together; match a speed band (keep up with a hull, don't outrun it); complementary roles |
| N14 | **cloak** | Cloak duty, cloaking energy/heat/fuel, cloaked firing and regen |
| N15 | **pilot** | Player flagship vs AI-flown escort vs carried craft |
| N16 | **weapon shape metrics** | Alpha damage (damage in the first N seconds, batteries included), area damage (blast radius × damage), anti-fighter value (fire rate, tracking, projectile speed), single-hit damage, range margin over the enemy |
| N17 | **weapon mix** | Share of weapon capacity on secondaries (min/max); energy-only (no ammo); missile-only |
| N18 | **hull damage cap** | Non-lethal: hull damage per second at most X, or never below the target's disable threshold |
| N19 | **mining** | Minable damage and prospecting metrics |
| N20 | **delays** | Shield delay, depleted shield delay and repair delay in the recovery and combat models |
| N21 | **overheat tolerance** | Allow running above 90% heat, with overheat damage rate counted |
| N22 | **new tags** | "ammo weapon", "self destruct", "gaslining", "spinal mount", "automaton", "homing", "blast" |
| N23 | **surplus metrics** | Fuel or energy beyond the ship's own needs (for tenders) |
| N24 | **hull choice** | Compare a shortlist of hulls for one role; allow superheavy |
| N25 | **target set** | Named targets for duels and counter-builds (generalises capture_targets) |
| N26 | **cloak duty** | Share of the time cloaked; cloaking energy, heat and fuel at that duty in the sustain and fuel checks; regen while cloaked (some cloaks set it to 0) |
| N27 | **exposure window** | Survive T seconds under a given incoming DPS: effective shields + hull against enemy DPS × (T + cloak transition times) |
| N28 | **loiter time** | Time on station: fuel and energy for T minutes at the given duties (cloak, cruise) without leaving |
| N29 | **jump denial** | How well the ship stops a target from jumping out: velocity kicks against the target's jump speed, how often, against its braking; plus disabling, overheating, fuel drain and slowing |
| N30 | **range coverage** | A capability (here jump denial) must hold at every range from point blank to the maximum, with no gap; maximise the maximum |

## Combat: general shapes

**1 Dedicated warship (line ship) — LC**
ship: combat, fight dedicated, weapons budget ≥ 85%
should: firepower 3, survivability 2, maneuverability 1
must: turn rate and acceleration ≥ 5th percentile
levers: none (this is the current warship role)

**2 Escort — LC**
ship: combat, fight escort, weapons budget ≥ 60%
should: survivability 2, firepower 2, speed 1
levers: N13 (keep up with the fleet's speed)

**3 Player flagship brawler — LC**
ship: combat, fight dedicated, hero, unique outfits
should: firepower 3, survivability 3, maneuverability 1
must: turn rate and acceleration ≥ 5th percentile
levers: N15 (pilot = player)

**4 Interceptor — LC**
ship: combat, fight N7 burst (~30 s)
should: acceleration 3, max speed 2, firepower 2
must: acceleration ≥ 75th percentile
levers: N7, N16 (projectile speed and fire rate already count in weapon value)

**5 Dogfighter — LC**
ship: combat, fight escort, evader
should: agility 3, firepower 2, survivability 1 (evasive route)
must: turn rate ≥ 75th percentile
levers: none

**6 Tank / brick — LC**
ship: combat, fight dedicated
should: survivability 3 (durable route forced), firepower 2
may: pull force
levers: forcing a route of a best-of composite (a role can't pick "durable" today; the solver chooses)

**7 Glass cannon / alpha striker — LU**
ship: combat, fight N7 burst (~20 s)
should: alpha damage 3 (N16), firepower 1
should not: mass
levers: N7, N16 (batteries count here)

**8 Long-range artillery / sniper — LU**
ship: combat, fight dedicated
should: firepower 3, survivability 1
must: every damage weapon's range ≥ 1000 (or a range-weighted firepower)
levers: N16 (range margin), a per-weapon must (all weapons meet X); today only ship totals can be required

**9 Close-range brawler — LU**
ship: combat, fight escort
should: firepower 3, survivability 2
levers: none; it needs the comfortable-range discount switched off (a "close range is fine" flag)

**10 Missile boat — LU**
ship: combat, fight dedicated, fights_per_restock 2
should: firepower 3, survivability 1
must: secondary share of weapon capacity ≥ 60% (N17)
levers: N17, N22 (homing tag)

**11 Torpedo bomber vs capitals — LU**
ship: combat, fight escort
should: single-hit damage 3 (N16), hull DPS 2, survivability 1
must: missile share ≥ 50% (N17)
levers: N6 (big targets), N16, N17

**12 Turret platform — LC**
ship: combat, fight dedicated
should: firepower 3, survivability 2
must not: guns (forbid fixed guns)
levers: a "fixed gun" tag (N22); arguably not a role but a hull-shape outcome

**13 Gunboat (forward guns only) — LC**
ship: combat, fight escort
should: firepower 3, agility 2
must not: turrets
levers: a "turret" tag (N22)

**14 Point-defence picket — LU**
ship: combat, fight escort
should: anti-missile 3, optical jamming 1, survivability 1
levers: none (anti-missile metric exists; jamming is an attribute)

**15 Anti-fighter / anti-drone screen — LU**
ship: combat, fight escort
should: anti-fighter value 3 (N16), survivability 1
levers: N6 (fighter swarm), N16

**16 Capital killer — LU**
ship: combat, fight dedicated
should: hull DPS 3, firepower 1, survivability 2
levers: N5 (relative hull damage), N6 (big targets)

**17 Pirate / bounty hunter — LC**
ship: combat, fight escort
should: firepower 3, speed 2, survivability 1
levers: none

**18 Raider (hit and run) — LU**
ship: combat, fight N7 burst
should: alpha damage 3, max speed 2, acceleration 1
may: afterburner
levers: N7, N16

**19 Blockade runner — LU**
ship: not combat
should: max speed 3, survivability 2, radar jamming 1, optical jamming 1
must: jumps ≥ 4
levers: none

**20 Kiter — LU**
ship: combat, fight dedicated
should: range margin 3 (N16), max speed 2, firepower 2
must: reverse thrust level useful
levers: N6 (enemy speed and range), N16

**21 Fleet anchor / carrier mothership — LU**
ship: combat, fight dedicated
should: survivability 3, bay count 3 (N12), firepower 1
levers: N12

**22 Fighter (carried) — LU**
ship: combat, fighter
should: firepower 3, agility 2
must not: drives, ramscoop (carried craft)
levers: N12 (the bay it fits), N15 (carried)

**23 Drone — UU**
ship: combat, fighter
should: firepower 3, agility 2
must: required crew 0 (automaton)
levers: N12, N22 (automaton)

**24 Mine layer — UU**
ship: combat, fight dedicated
should: area damage 3 (N16), survivability 1
must: has Korath mines (or a "mine" tag)
levers: N16, N22; mines need their own model (stationary submunitions)

**25 Nuke boat — UU**
ship: combat, fight N7 burst
should: area damage 3, max speed 1
levers: N16, N22 (blast); a "triggers nuke alert" consequence (AI reacts)

**26 Swarm-buster — UU**
ship: combat, fight escort
should: area damage 3 (N16), firepower 1
levers: N6 (clustered swarm), N16

## Combat: disable, capture, plunder

**27 Disabler — LC**
ship: combat, fight escort, goal disable
should: firepower 3 (goal disable weights shield damage up), survivability 2
levers: none (goal disable exists)

**28 Boarding flagship — LC**
ship: combat, fight dedicated, goal disable, hero
should: capture strength 3 (N11), firepower 2, survivability 2
must: bunks ≥ 2 × required crew
levers: N11 (Hand to Hand outfits in the pool: see the open question below)

**29 Capture-intact specialist — UU**
ship: combat, goal capture-intact, capture_targets [named hull]
should: firepower 3, survivability 1
levers: none (exists)

**30 Plunderer / looter — LU**
ship: combat, fight escort, goal disable
should: firepower 2, cargo space 2, survivability 1
must: has tractor beam
levers: none

**31 Post-battle scavenger — LU**
ship: not combat
should: survivability 3, maneuverability 2
must: has tractor beam, reverse thrust balanced; emphasize cargo space
may: push force
levers: none (current scavenger role)

**32 Shield stripper support — LU**
ship: combat, fight escort, goal disable
should: shield DPS 3, survivability 1
should not: hull DPS
levers: none

**33 Shield breaker (disruption) — UU**
ship: combat, fight escort
should: disruption DPS 3 (N5), survivability 1
levers: N5

**34 Ion drainer — UU**
ship: combat, fight dedicated
should: ion DPS 3, scrambling DPS 1 (N5), survivability 1
levers: N5, N6 (targets with weak power)

**35 Heat killer — LU**
ship: combat, fight dedicated
should: heat DPS 3, burn DPS 1 (N5), survivability 1
must: own heat stays below 90% while firing (already a check)
levers: N5, N6 (targets with low heat capacity)

**36 Snare — UU**
ship: combat, fight escort
should: slowing DPS 3 (N5), range 1, survivability 1
levers: N5

**37 Grappler — UU**
ship: combat, fight dedicated
should: pull force 3, survivability 2, firepower 1
levers: none

**38 Repulsor — UU**
ship: combat, fight escort
should: push force 3, max speed 1, survivability 1
levers: none

**39 Damage-over-time attacker — UU**
ship: combat, fight dedicated
should: corrosion, leak, burn and discharge DPS 3 (N5)
levers: N5 (discharge and leak have 0 outfits in play: no pass needed)

**40 Fuel stranding attacker — UU**
ship: combat, fight escort
should: fuel damage DPS 3 (N5), max speed 1
levers: N5

**41 Energy drainer — UU**
ship: combat, fight escort
should: energy damage DPS 3 (N5)
levers: N5 (one outfit in play)

**42 Giant-killer by percentage — UU**
ship: combat, fight dedicated
should: relative shield and hull damage 3 (N5)
levers: N5, N6 (big targets); 0 outfits in play today

## Defence and survival

**43 Shield tank with protection — LU**
ship: combat, fight dedicated
should: shield regen 3, effective shields 2, firepower 1
levers: none

**44 Hull tank — UU**
ship: combat, fight dedicated
should: hull repair 3, effective hull 2, firepower 1
levers: none

**45 Fast-recovery skirmisher — UU**
ship: combat, fight escort
should: survivability 2, firepower 2
should not: shield delay, depleted shield delay, repair delay
levers: N20

**46 Missile-proof brick — LU**
ship: combat, fight dedicated
should: anti-missile 3, radar jamming 2, survivability 2
levers: N6 (missile swarm)

**47 Ion-hardened — UU**
should: ion protection 2, ion resistance 2, energy capacity 1 (on top of a combat role)
levers: N6 (Ka'het/ion enemies); better as an enemy-profile overlay than a role

**48 Heat-hardened — UU**
should: heat capacity 2, heat protection 2 (overlay)
levers: N6; heat protection has 0 outfits in play

**49 Exotic-resistant — UU**
should: corrosion, leak, burn, discharge protection 2 (overlay)
levers: N6

**50 Overheat-tolerant berserker — UU**
ship: combat, fight dedicated
should: firepower 3
levers: N21 (relax the 90% heat rule)

**51 Disable-resistant — UU**
should: effective hull 2
should not: threshold percentage, disabled recovery time
levers: N20

## Stealth, sensors, electronic warfare

**52 Smuggler — LU**
ship: not combat
should: cargo scan opacity 3, outfit scan opacity 2, scan interference 2, cargo space 2, speed 1
levers: none (all attributes)

**53 Cloaked ambusher — UU**
ship: combat, fight N7 burst
should: alpha damage 3, cloak 1
must: has cloak
levers: N14, N16; cloak has 0 outfits in play

**54 Cloaked scout / courier — UU**
ship: not combat
should: speed 2, jumps 2
must: has cloak
must not: damage weapon
levers: N14

**55 Electronic-warfare escort — UU**
ship: combat, fight escort
should: radar jamming 3, optical jamming 3, survivability 1
levers: none; jamming protects only the ship that carries it, so a "fleet jammer" may not exist (open question)

**56 Scanner / survey ship — LU**
ship: not combat
should: outfit scan power 2, cargo scan power 2, tactical scan power 1, speed 1
levers: none

**57 Bounty tracker — UU**
ship: combat, fight escort
should: tactical scan power 2, speed 2, firepower 1
levers: none

## Trade, transport, travel

**58 Bulk freighter — LC**
ship: not combat
should: cargo space 3, survivability 1, speed 1
levers: none (current freighter role)

**59 Armed merchant — LC**
roles: freighter + escort (current two-role combination)
levers: none

**60 Fast courier — LC**
ship: not combat
should: max speed 3, jumps 2, acceleration 1
must: cargo space ≥ 20
levers: none

**61 Passenger liner — LC**
ship: not combat
should: bunks 3, survivability 1
levers: none; "comfort outfits" (holographic entertainment) only as an attribute

**62 Mixed cargo and passengers — LU**
should: cargo space 2, bunks 2, survivability 1
levers: none

**63 Peaceful-area freighter — LU**
ship: not combat
should: cargo space 1; deprioritize maneuverability
must: cargo space ≥ 1000, jumps ≥ 6
must not: jump drive, anti-missile
should not: reverse thrust (pending the user's answer: was this only an example?)
levers: none (current role)

**64 Fleet supply hauler — LU**
should: cargo space 3, survivability 1
must: speed ≥ the fleet's speed (N13)
levers: N13

**65 Fuel tanker — LU**
should: fuel surplus 3 (N23), ramscoop 1
levers: N23; fuel transfer only happens to disabled allies, so this may be niche

**66 Long-range explorer — LU**
ship: long_range
should: jumps 3, fuel generation 1, survivability 1
levers: none

**67 Dark-space explorer — UU**
ship: long_range, light dark (N9)
should: jumps 3, fuel generation 2
levers: N9

**68 Jump-drive scout — UU**
should: jump range 2, jumps 2, speed 1
must: has jump drive
must not: hyperdrive
levers: none

**69 Mission ferry — LU**
ship: not combat
should: bunks 2, survivability 3
levers: none

## Mining and industry

**70 Miner — LU**
ship: not combat
should: minable damage 3 (N19), asteroid scan power 1, cargo space 2
must: has tractor beam
levers: N19

**71 Defended miner — UU**
roles: miner + escort
levers: N19

**72 Prospector scout — UU**
should: asteroid scan power 3, speed 1
levers: none

## Economy, progression, availability (overlays: combine with any role)

**73 Starting-ship upgrade — LC**
must: cost ≤ starting credits (N1); availability sold only (N10), no military licences
levers: N1, N10

**74 Budget build — LC**
must: cost ≤ X (N1)
levers: N1

**75 Cheapest ship that passes — LU**
should not: cost 3 (N1); the rest of the role as musts only
levers: N1, a "musts only, then minimise cost" mode

**76 No-budget endgame — LC**
ship: unique outfits on
levers: none (default)

**77 Licence-limited mid game — LC**
levers: none (licence settings exist, but globally; per request needs N10)

**78 Faction-locked build — LU**
levers: N10 (source group or faction per request)

**79 Plunder-only build — UU**
levers: N10

**80 Re-buyable build — LU**
levers: N10 (sold only)

**81 Mass-produced escort — LU**
must not: unique outfits
levers: N10 (sold only), N1 (per-copy cost)

**82 Hero flagship with story uniques — LU**
ship: hero, unique outfits
levers: none

**83 Story mission constraints — LU**
must: min bunks / cargo space (mission values)
levers: none

**84 Refit an existing ship — LC**
levers: N4 (installed outfits kept or swapped at a cost)

**85 Partial refit — LU**
levers: N4 (vary one family only)

## Mobility specifics

**86 Top-speed racer — UU**
should: max speed 3, acceleration 1
levers: none

**87 Agility king — UU**
should: agility 3, turn rate 1
levers: none

**88 Reverse-thrust kiter — UU**
should: reverse acceleration 2, agility 2, firepower 2
must: reverse thrust nimble
levers: none

**89 Afterburner sprinter — LU**
should: speed 3
must: has afterburner
levers: none, but the afterburner's real effect isn't in the speed metric today (thrust only while burning fuel)

**90 Heavy hauler that still turns — LC**
roles: freighter
must: turn rate ≥ 25th percentile
levers: none

**91 Fleet-speed matcher — LU**
must: max speed within ±5% of a named hull's (N13)
levers: N13 (a target band, not "more is better")

## Environment (overlays)

**92 Bright-star operations — UU** — light bright (N9)
**93 Must run dark — UU** — must_run_dark (exists; N9 would generalise it)
**94 Dim-star evader — UU** — evader + light dim (N9)
**95 Low solar-wind regions — UU** — solar wind low (N9); should: fuel capacity, fuel generation
**96 Long fights (sieges) — UU** — fight N7 siege (~600 s)
**97 Short skirmishes — LU** — fight N7 burst (~30 s)
**98 Many fights between restocks — UU** — fights_per_restock 5 (exists)
**99 Energy weapons only — LC** — must not: ammo weapon (N22 tag)
**100 Ammo-heavy, energy-light — UU** — should not: energy generation; must: secondary share ≥ 50% (N17)

## Hull shapes

These are facts about the hull, not instructions. The user picks the hull; the tool adapts.

**101–109 Tiny / medium / capital / gun-heavy / turret-heavy / special slots / engine-starved / weapon-starved /
very heavy** — no levers; they matter to pruning bands and to which outfits fit.
**110 Shortlist of hulls — LC** — N24 (run one role over several hulls, rank them)
**111 Fleet of complementary hulls — UU** — N13

## Added from the optimizer session's first list (A1–A45)

**A1 Flotsam farmer of a specific drop** — should: alpha damage 2, tractor beam 2, cargo space 1; N6 (named target), N25
**A2 Gas-giant lander** — must: has gaslining (attribute; N22 tag would be neater)
**A3 Research vessel** — must: has Research Laboratory (by name); levers: must have a named outfit (NEW: name-level must)
**A4 Decoy tank** — should: survivability 3; may: decoy plating (attribute); the decoy's effect on AI targeting isn't modelled
**A5 Self-destruct decoy** — must: has self destruct (N22); cheap (N1)
**A6 Holovid / Phantom Pallet trickster** — should: cargo scan opacity, outfit scan opacity (as smuggler 52)
**A7 Anti-cloak hunter** — should: tactical scan power; unclear whether the game has cloak detection (open question)
**A8 Scrambler** — should: scrambling DPS 3 (N5)
**A9 Beam boat** — must: every damage weapon instantaneous (tag allow instantaneous, forbid the rest)
**A10 Missile-only ship** — must: every damage weapon missile (tag); N17
**A11 Mixed primaries + secondaries** — must: secondary share 20–50% (N17)
**A12 Gravity anchor** — should: push force 2, pull force 2, survivability 2
**A13 Disruptor + hull combo** — should: disruption DPS 2, hull DPS 2 (N5); a synergy term (product composite exists)
**A14 Spinal-mount warship** — must: has spinal-mount weapon (N22); only on hulls with the slot
**A15 Cloaked transport** — must: has cloak; should: cargo space 3 (N14)
**A16 Escort-carrier hybrid** — fight escort; should: bays 2 (N12), survivability 2
**A17 Carrier + its fighters designed together** — N12, N13
**A18 Fleet line ship flown by AI** — N15 (pilot AI)
**A19 Hero all-rounder** — roles warship + freighter + escort, hero (exists)
**A20 Stock-loadout upgrade** — N4 with the stock loadout as the installed set
**A21 Upgrade path (next affordable step)** — N1 + N4
**A22 Speedrun (best design before a story point)** — N10 (event-gated)
**A23 Arena duel vs a named hull** — fight dedicated; N6 from the hull, N25
**A24 Counter-build vs a named government** — N6 from the government's fleets, N25
**A25 Siege vs station defences** — N7 siege; should: range margin (N16)
**A26–A31 Faction-tech builds (Wanderer, Hai, Pug, Coalition/Heliarch, Korath territory, Remnant space)** — N10 (source group per request); Korath territory and Remnant space also N6
**A32 Human-tech purist / one-race showcase** — N10
**A33 Source- and government-limited availability** — exists globally; N10 per request
**A34 Quarg hunting** — governments setting (exists); N6 (huge shield-heavy targets)
**A35 Max cargo, no weapons** — should: cargo space 3; must not: damage weapon (tag exists)
**A36 Max jump range** — should: jumps 3 (exists)
**A37 Max bunks** — should: bunks 3 (exists)
**A38 Immobile regen fortress** — should: shield regen 3, hull repair 2; no agility floor; must not: needs_drives? (a station-like ship)
**A39–A41 Minimum mass / heat / energy ships** — should not: mass, heat generation, energy consumption (attributes; the sign is the question)
**A42 Zero-crew automaton** — must: required crew 0 (N22 automaton)
**A43 Superheavy hulls** — N24 (allow superheavy; currently excluded by the user's rule)
**A44 Unique-only stress test** — unique outfits on; a test case, not a role
**A45 Fleet repair tender** — not real (merged into 124 and "carrier as repair base")

## Added in the optimizer session's reply (112–155)

**112 Anti-Korath** — overlay: N6 Korath preset (heat, push, slowing protection)
**113 Anti-Ka'het** — overlay: N6 Ka'het preset (ion protection, energy reserve)
**114 Counter-build from a named government's hulls** — N6 from data, N25
**115 Duel vs one named hull** — N6, N25 (same as A23)
**116 Missile-heavy enemies, no anti-missile licence** — N6 missile swarm; should: radar jamming 3
**117 Multi-wave defence** — N7 chain (3 × 90 s, short recovery)
**118 Endurance patrol** — N7 chain (many short fights), fights_per_restock high
**119 Station or planet siege** — N7 siege, N16 range margin (same as A25)
**120 Ambush survival** — N8 (start hot, bright star)
**121 Never kill by accident** — goal disable + N18 hull damage cap
**122 Pacifist** — must not: damage weapon; should: push force, tractor beam, anti-missile
**123 Crew transport for a capture fleet** — should: bunks 3, survivability 1
**124 Rescue and refuel tender** — should: fuel surplus (N23), speed 2
**125 Aggro tank protecting the flagship** — can't be modelled: AI targeting
**126 Escorts covering the flagship's weaknesses** — N13 (fleet)
**127 Escort-carrier hybrid** — same as A16
**128 Drone carrier** — N12 (drone bays)
**129 Fighter for a specific bay type** — N12 (bay type), fighter
**130 Hyperdrive-only cheap trader** — must not: jump drive (exists)
**131 Jump-drive-only explorer** — must not: hyperdrive (exists, if "hyperdrive" works as a must_not metric)
**132 Jump-fuel economy** — should not: fuel per jump (attribute) — sign of a cost, as A39–A41
**133 Next affordable upgrade step** — N1 + N4 (same as A21)
**134 Resale-aware design** — N3
**135 Crew-salary-aware design** — N2
**136 Reserve outfit space** — must: free outfit space ≥ X (exists)
**137 Warship with spare cargo for plunder** — warship + must: cargo space ≥ X (exists)
**138 Carries outfits as cargo for another ship** — must: cargo space ≥ X (exists)
**139–144** — as A2–A5 and A42 (attribute musts)
**145 Cloaked repair** — N14 (cloaked regen/repair multipliers)
**146 Mission scanner** — as 56
**147 Anti-cloak hunter** — as A7
**148 Mining drone fleet** — N12 + N19
**149 Overheat-safe star-hugging miner** — miner + N9 star-hugging
**150 Named story variant hull** — no levers (hull choice)
**151 Event-gated speedrun** — N10 (same as A22)
**152 Sold-only, can rebuy** — N10 (same as 80)
**153 Plunder-only flex build** — N10 (same as 79)
**154 Superheavy hull** — N24 (same as A43)
**155 Every unique allowed** — same as A44

## Added by the user (U1–U2)

### U1 Third-party combat vulture — LC

A ship of a third faction, hostile to both sides of a permanent war zone. It stays cloaked most of the time, and
uncloaks only to loot: board disabled ships to plunder them (no captures) and pull in flotsam. It stays in the system
until its cargo is full.

ship: not combat; no weapons at all, not even anti-missile (needs_anti_missile off)
should: cargo space 3, maneuverability 3 (match velocity and dock fast), effective shields + hull 3, tractor beam 2,
shield regen 1 (it can fly away from the action, uncloak and pause a few seconds to recover)
must:
- has cloak (hull or outfit). If the hull can't cloak and no cloaking outfit is available, the answer is "this hull
  can't do this job" (a first-class result)
- fuel and energy income (ramscoop, fuel generation) keep up with cloaking at ~80% duty indefinitely (N26), using
  the war zone's star and solar wind
- survives 7 s uncloaked under the war zone's incoming DPS (N27); cloak and uncloak time is not counted
- has tractor beam
must not: damage weapon, anti-missile; needs_regen as a hard rule (recovery is optional, see above)
should not: mass
levers: N26, N27, N6 from data (the war zone's fleets), and the system's star for solar and wind (N9)

War zones, for now (from the 0.11.2 map data):
- **Wah Ki (Hai space):** Hai fleets ("Small Hai", "Large Hai" and merchants) against Hai (Unfettered) ("Large
  Plundering Unfettered", and the "Unfettered Hai Space Raid").
- **Mesuket and around:** "Large Kor Mereti" against "Large Kor Sestor".

The incoming DPS comes from those fleets' stock loadouts, computed with the calculator. The vulture is under fire
from 1–3 ships at a time (user). So the exposure check uses the combined DPS of the 3 strongest ships that appear in
those fleets: the worst case of the range. The 1-ship case can be reported as a margin.

What the game says (checked in the source):
- **Can't loot while cloaked.** Boarding needs "cloaked boarding" and picking up flotsam needs "cloaked pickup"; no
  outfit or hull has either.
- **Cloak sources.** One outfit, the Cloaking Device: Unique, a Free Worlds mission reward, also on a Pug ship. Native
  cloaking hulls: Remnant, Drak, Ka'het, Bunrodea, Successor.
- **The Cloaking Device costs:**
  - 1 energy per frame (60/s) and 0.2 fuel per frame (12 fuel/s);
  - no regeneration while cloaked (multipliers −1);
  - ~1.7 s to cloak and the same to uncloak.

  Keeping it on means a large ramscoop or fuel generation. Remnant hulls burn 0.05–0.1 fuel per frame (3–6/s).

### U2 Fight anchor — LU

Keeps enemy ships from jumping out until the rest of the fleet disables or destroys them. The anchor does not try to
disable anything itself. Enemy combat AI fights until it's close to being disabled, then tries to jump out; the
anchor stops that second step. There's usually one per fleet, so it should cover as much of the battle as it can.

ship: combat, fight dedicated
should: jump denial 3 (N29), denial range 2 (N30), survivability 2
must:
- jump denial holds from point blank to the maximum range, with no gap (N30); as much range as possible
- denial weapons are turrets or otherwise cover all directions
may: fuel drain (fuel damage DPS, N5), slowing DPS (backup strategy), pull force
should not: putting the targets out of range (pushes can drive them away; pulls keep them in)
levers: N29, N30, N5, N6 (targets: stock warships by mass band)

How it stops a jump, in order of importance (`Ship::IsReadyToJump`, `Ship::ApplyForce`):
1. **Keep the target moving (main focus).** A ship can only jump at or below its drive's jump speed: 0.2 px/frame
   for the hyperdrive (12 px/s), 0.3 for the jump drive (18 px/s). Each hit with hit force adds force ÷ the target's
   inertial mass to its velocity. It then has to brake below the jump speed again. So denial = hits often enough
   that it never gets below. No weapon in 0.11.2 is "gravitational" (mass-independent; only hazards are), so heavy
   targets need much more force.
2. **Drain its fuel (main focus).** Drain the fuel below the jump cost (100 for a hyperdrive, 200 for a jump drive)
   before the target decides to flee. Fuel damage weapons in 0.11.2: Ember Tear (Remnant, secondary), Celestial
   Culverin (Quarg), Nucleolysis Beam (Aberrant flotsam). Fuel protection resists it.
3. **Keep a hyperdrive ship from facing its destination (backup).** For early game and weaker hulls: slowing
   damage cuts its turn rate. It doesn't work against jump drives or scram drives, so not against the most advanced
   ships.

Not part of the role: disabling and overheating (the fleet does that), and departure distances (ignored).

Pruning note: PR #2's damage lens drops the Nucleolysis Beam (beaten by the Ka'het Ravager Beam on damage) because
the lens ignores fuel damage. For this role that's one of only three fuel-drain weapons.

## Lever demand (how many scenarios need each new lever)

Rough counts, after merging duplicates:

| Lever | Scenarios | Notes |
|---|---|---|
| N10 availability mode | ~15 | Overlays; cheap to build on the existing availability code |
| N6 enemy profile | ~15 | The biggest modelling step; unlocks counter-builds |
| N5 effect damage | ~12 | Mostly metrics on weapon stats |
| N7 fight shape | ~10 | Burst and siege are a few lines each; chains need the sustain model extended |
| N16 weapon shape metrics | ~10 | Alpha and range margin are the most used |
| N1 cost | ~8 | Contradicts the earlier "budgets are ignored" decision |
| N13 fleet | ~7 | Speed matching is small; joint design is large |
| N12 bays | ~6 | Large |
| N22 new tags | ~8 | Small |
| N17 weapon mix | ~5 | Small |
| N4 installed | ~5 | Medium; also changes pruning (installed outfits never pruned) |
| N9 light | ~5 | Small: the solar factors already exist as constants |
| N11 capture strength | ~3 | Needs a decision on Hand to Hand outfits |
| N14 cloak | ~5 | No cloak outfits in play today |
| others (N2, N3, N8, N15, N18–N21, N23–N25) | 1–3 each | |
