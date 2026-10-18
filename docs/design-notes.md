# Design notes

Decisions and game knowledge the optimizer has to respect. Formulas cite the game source they come from.

## Hulls are designed empty

- A hull's own stats come from its `attributes` block. Stock outfits are a separate list and are never added in.
- Design on ship models only. Variants can change the hull itself through `add attributes`.

## Availability is the user's choice

- The user says which outfits and hulls are in play. Nothing is assumed from shops.
- Presets are conveniences for filling that choice in, e.g. "everything sold at these outfitters" or
  "everything unlocked by this story point". They never restrict it on their own.

## Requirements are on stats, not outfit names

"Needs reverse thrusters" means the ship needs `reverse thrust`, from whatever outfit provides it
(32 outfits do, including combined drives such as the Graviton thrusters and the Fusion Drive).
"Needs tractor beams" means total `tractor beam` strength, which is a weapon stat
(currently the Tractor Beam and the Horizon Grappler, both turrets).

## Displayed values vs. data values

The game shows movement stats scaled from the data values
(`OutfitInfoDisplay.cpp` SCALE, `ShipInfoDisplay.cpp`):

| Stat | Outfitter shows | Ship info shows |
|---|---|---|
| `thrust`, `reverse thrust` | value × 3600 | 3600 × thrust × (1 + acceleration multiplier) / mass |
| `turn` | value × 60 | 60 × turn × (1 + turn multiplier) / mass |
| max speed | | 60 × thrust / drag |

Mass here is divided by (1 + inertia reduction). Turn and acceleration are divided by the same mass, so
comparing displayed turn with displayed acceleration does not depend on mass.

## Reverse thrust rules (from play experience)

With T = thrust, R = reverse thrust, U = turn (data values, multipliers applied), d = drag:

1. **Useless threshold.** Reverse thrust only helps if it stops the ship faster than turning 180° and
   burning the main engines. From top speed (T / d per frame) and ignoring drag while stopping:
   reverse wins when R > T·U / (U + 180·d). Mass cancels out.
2. **Balanced.** Displayed reverse acceleration equals displayed turning: 3600·R = 60·U, so R = U / 60.
3. **Nimble.** Displayed reverse acceleration is about halfway between displayed turning and displayed
   acceleration: R ≈ (U / 60 + T) / 2.

Except for specific combat roles, rule 1 is the floor. Rules 2 and 3 are target levels a role can ask for.
Reverse thrust also costs `reverse thrusting energy` and `reverse thrusting heat`.

Example, stock Argosy (T 38.85, U 885, d 7.4): useless below R 15.5, balanced at 14.75, nimble at 26.8.
It carries R 21.75.

## Obsolete-outfit pruning

- **Always safe:** A makes B obsolete if A is at least as good on every stat and uses no more of anything.
  Run after the availability filter. A stat an outfit doesn't have counts as 0, so if B has a useful stat A
  lacks (B's energy capacity on a generator, say), A can't make B obsolete. Every stat needs a direction (more
  is better, less is better); stats with no known direction must be equal, so they never cause wrong pruning.
- **Per role:** compare only the stats the role cares about. Prunes more, valid for that request only.
- Needs a table saying whether each attribute is good, bad or neutral.
- "Better per ton" is not a safe basis for pruning.

## Outfits needing special handling

Flagged from play experience. Each needs its behaviour worked out before the optimizer may pick it.

| Group | Outfits in current data |
|---|---|
| Shield cortexes | "Byiaa", "Ej", "Jaase", "Jorv" Shield Cortex; Shield Cortex Interface |
| Active cooling | 11 outfits with `active cooling` (Cooling Module, Thermoelectric Cooler, hybrid cooling, …) |
| Ramscoops (diminishing returns) | 9 outfits with `ramscoop` (Ramscoop, Catalytic Ramscoop, Magnetic Scoop, …) |
| Specific weapons | Grab-Strike Turret, Cluster Mine Layer, Heliarch Attractor |
| Solar | Solar Cell, Solar Battery, Concentrating Solar Cell/Array, KP-6 Photovoltaic Panel/Array, Collector Modules, laminas, … |
| Optical lasers | Blue Optical Laser, Green Optical Laser, Optical Lasing Generator |
| Lamina | Radiative, Concealment, Photoelectric Lamina |
| Torch engines and injectors | Z-333/666/999 Fusion Torches, Z-3600 Amat Torch, RG3/15/18 Torch Thruster and Steering, Ion Torch, Remass Injector |
| Multimodal armor | Resilient, Light, Heavy, Regen, Keystone |
| Bunrodea reactors | Quark Reactor, Electroweak Reactor, with Reactor Limiter and Reactor Overclocker |
| Bunrodea shields | Small/Large Shield Relay, with Shield Relay Limiter and Booster |
| Bunrodea repair | Small/Large Nanite Fabricator, with Nanite Limiter and Enhancer |
| Illegal outfits | Nerve Gas, Microbot Defense Station (`illegal` stat); see "Illegal outfits and contraband" |

Also found in the data:

- 48 weapons need separate ammunition outfits.
- 60 outfits require crew, which needs bunks.
- Outfits Expansion, Mass Expansion and Cargo Expansion convert capacity. Outfits Expansion adds
  `cooling inefficiency`, which feeds a non-linear heat formula (`ship/ShipAttributeCache.cpp`).
- 7 outfits need a spinal mount.
- Minerals have `installable -1`. About 150 entries have no category and are not installable.
- Only one copy is useful for some outfits, e.g. hyperdrives and jump drives.

## Illegal outfits and contraband

- **Illegal** means installed outfits (the `illegal` stat). **Contraband** means cargo.
- Either one is a design decision the role spec has to answer:
  1. The ship never enters controlled space: no constraint.
  2. The ship has a cloak: no constraint, though the cloak's energy and fuel costs count.
  3. Otherwise the spec states a plan: disguise, speed, weapons, or a combination.

Game mechanics behind those plans (`Politics.cpp`, `Ship::Scan` in `Ship.cpp`):

| Mechanic | Effect |
|---|---|
| `inscrutable` | Outfit scans always fail. |
| `scan interference` (Decoy Plating gives 2) | Each outfit scan succeeds with chance 1 / (1 + interference): 1 Decoy Plating evades 67% of scans, 2 evade 80%. Cargo scans use the same divisor. |
| `scan concealment` | That many tons of contraband are hidden completely. |
| Legal cargo | Contraband mixed with enough legal cargo lowers the cargo-scan chance. |
| `cargo scan opacity`, `outfit scan opacity` | Each point counts as an extra ton to scan, so scans take longer. This helps a speed plan escape before the scan finishes. |

## The game's fit rule

`Outfit::CanAdd` and `MINIMUM_OVERRIDES` in `Outfit.cpp`: after adding an outfit, every attribute must
stay at or above 0, except a listed set that may take any value (energy, heat and fuel generation and
consumption, `shield energy`, `hull energy`, thrusting side effects, …). `required crew` must stay at or
above 1 unless the ship is an automaton. The optimizer applies exactly this rule, which also covers every
"slot" style mechanic below without special code.

## Bunrodea reactors, shield relays and nanite fabricators

The base outfit provides upgrade slots as an attribute (`reactor upgrades`, `relay upgrades`,
`nanite upgrades`). Limiters and boosters use them up. There is no other code for these attributes, so:

- Slots are pooled across the ship. Two Small Shield Relays give 12 relay slots shared by all boosters and
  limiters; a modifier is not tied to one unit.
- Modifiers are flat, ship-wide stat changes. They can be mixed freely within the slot limit.
- The generic fit rule enforces everything, e.g. a limiter can't be fitted without the slots a base unit provides.

| Base unit | Slots | Stats |
|---|---|---|
| Quark Reactor | 6 reactor | +8.35 energy, +10.9 heat |
| Electroweak Reactor | 18 reactor | +17.25 energy, +20.5 heat |
| Small Shield Relay | 6 relay | +0.65 shield gen, 0.6 shield energy |
| Large Shield Relay | 16 relay | +2 shield gen, 1.6 shield energy |
| Small Nanite Fabricator | 4 nanite | +0.72 hull repair, 1.08 hull energy |
| Large Nanite Fabricator | 10 nanite | +2.12 hull repair, 3.18 hull energy |

| Modifier | Slots | Space | Stats |
|---|---|---|---|
| Reactor Limiter | 2 | 2 | −0.55 energy, −6.6 heat |
| Reactor Overclocker | 3 | 4 | +0.9 energy, +3.15 heat |
| Shield Relay Limiter | 1 | 1 | −0.02 shield gen, −0.1 shield energy |
| Shield Relay Booster | 1 | 2 | +0.4 shield gen, +1.2 shield energy |
| Nanite Limiter | 1 | 2 | −0.025 hull repair, −0.2 hull energy |
| Nanite Enhancer | 2 | 5 | +0.25 hull repair, +0.75 hull energy |

Notable extremes:

- A fully limited reactor has negative heat generation: Quark + 3 limiters gives 6.7 energy and −8.9 heat;
  Electroweak + 9 limiters gives 12.3 energy and −38.9 heat. Heat generation may go negative, so this is
  legal and acts as cooling.
- A fully limited shield relay uses no energy: Small + 6 limiters gives 0.53 shield gen for 0 energy,
  Large + 16 limiters gives 1.68 for 0.
- The Nanite Limiter's description mentions heat efficiency, but its data has no heat effect. Data wins.

## Environment-dependent outfits (solar, ramscoop, laminas)

Formulas (`System::GetSolarGeneration`), per frame, summed over every star in the system:

- scale = 0.2 + 1.8 / (0.001 × distance to star + 1): 2.0 on top of the star, 1.1 at 1000, 0.8 at 2000, toward 0.2 far away.
- energy += star power × `solar collection` × scale
- heat += star power × `solar heat` × scale
- fuel += 0.03 × star wind × scale × system ramscoop multiplier × √(total `ramscoop`). The square root is the
  diminishing return: 4× the ramscoop gives 2× the fuel. `fuel generation` is a separate flat bonus.

Star power × scale at the system centre, across 694 systems with stars:
min 0, quartiles 1.44 / 2.0 / 3.21, max 24.5 (Eta Carinae). Sol is 2.0. Wind × scale: quartiles 1.32 / 1.8 / 3.0, Sol 1.28.

Outfits:

- Solar collection: Solar Cell, Concentrating Solar Cell/Array, Small/Large Collector Module, KP-6 Photovoltaic Panel/Array, Photoelectric Lamina.
- Solar heat as a side effect: Radiative and Concealment Lamina, Magnetic and Plasmadyne Scoop, Successor Fuel Sail.
- Ramscoop: Ramscoop, Catalytic Ramscoop, Emergency Ramscoop, Wanderer Ramscoop, Fuel Processor, Magnetic Scoop,
  Plasmadyne Scoop (also needs a spinal mount and a gun port), Successor Fuel Sail, Afterburner (Asteroid Class).
- Slot mechanics, handled by the generic fit rule: the Solar Battery provides 36 `solar cell` slots that Solar Cells use.
  Laminas use an `anchor point` (0 outfit space); only 16 hulls have anchor points.
- The ship info screen counts `solar collection` and `solar heat` at factor 1 (`ShipInfoDisplay.cpp`), but in
  flight they are multiplied by star power × scale (`Ship.cpp`, per-frame update). At Sol's centre that is ×2.
- Fighters carried in a bay collect no solar energy or ramscoop fuel.

### Heat model (needed by the solar rules)

`Ship.cpp`, `Entity.cpp`: each frame heat −= heat × 0.001 × `heat dissipation`; the ship overheats (is disabled)
above max heat = 100 × (mass + cargo + `heat capacity`) and recovers below 90% of it. So with a constant net heat
input Q per frame, heat settles at Q / (0.001 × dissipation): the steady state is safe when
Q ≤ 0.1 × dissipation × (mass + heat capacity) (empty cargo, the worst case). A short exposure is safe if heat,
rising exponentially toward that level from the idle level, stays below max heat for the exposure time.
Active cooling depends on the heat level and is covered with the cooling category.

### Solar rules (decided)

Star power percentiles are over the 686 systems with a star (8 systems are dark); a multi-star system's power
is the sum of its stars. Distance factor = 0.2 + 1.8 / (0.001 × distance + 1). Each rule is checked at the
boundary distance that is worst for it.

| # | Who | Condition | Effective solar factor | Check |
|---|---|---|---|---|
| 1 | Ships passing through | One dark system, not two in a row | 0 | Energy reserves cover idle use + thrusting for one system's transit time |
| 2a | All ships | Pass a 90th-percentile star (power 2.67) at 500–1000 | 2.67 × 1.40 = 3.74 | No overheating during the transit time |
| 2b | All ships | Stay near a 75th-percentile star (power 1.7) beyond 750 | 1.7 × 1.23 = 2.09 | Steady-state heat below max heat |
| 3 | Evading ships | Stay beyond 5000 from a 20th-percentile star (power 0.7) | 0.7 × 0.5 = 0.35 | Steady-state energy ≥ 0 for idle use + cloak (if fitted) |
| 4 | Combat ships | At 3000 or more from a 30th-percentile star (power 0.76) | 0.76 × 0.65 = 0.49 | Steady-state energy ≥ 0 with all weapons firing plus the largest of: shield + hull regeneration, thrust, turning |
| 5 | Ships that must run in the dark | | 0 | No solar collection counted; solar outfits excluded |

### Ramscoop rules (decided)

1. Every ship has some ramscoop (total > 0; the smallest source is 0.25) unless the role says otherwise.
2. Ships meant to travel long distances fast, or through lots of hostile space, regenerate enough fuel that
   they never need to refuel at a planet or station.
3. Ships that spend fuel on more than jumping (afterburners, `fuel energy`, shield/hull fuel, cloaking fuel)
   should have ramscoops to recover those losses: use is bursty, recovery is smooth.

Star wind percentiles (same systems): 20th 0.64, 30th 0.75, median 0.9, 75th 1.57, 90th 2.14.

### Transit time (input to solar rule 1, 2a and ramscoop rule 2)

Depends on: the drive used (hyperdrive, scram drive or jump drive), the speed the ship enters the system with,
and how fast it can cancel that speed (turning, thrust, reverse thrust). To be worked out with the jump rules.
Game facts so far (`Ship::DoHyperspaceUpdate`): hyperdrive arrivals leave hyperspace at max(2, max speed) heading
into the system; jump drive arrivals are placed 300–600 units from the target plus the system's arrival distance.
Arrival distance = the system's habitable value clamped to 500–5000; minimum departure distance is 0 (1000 in 8 systems).

### Ramscoop rule 2: refuel one jump in about 2 seconds of fast-forward

Fast-forward runs 3 game frames per drawn frame (`main.cpp`), so 2 seconds = 360 frames. While refuelling the ship
is not stationary: the pilot keeps it as close to the star as reasonably possible with repeated flybys and orbits,
roughly 5 to 100 from it. The check uses the distance factor averaged over that range, 1.911:
0.03 × W × 1.911 × √(ramscoop) × 360 + 360 × `fuel generation` ≥ fuel for one average jump.
Without fuel generation that is √(ramscoop) ≥ jump fuel / (20.64 × W).

W is the best star wind reachable, which improves with the number of jumps N the ship's fuel allows
(user's measurement, used as given). Ramscoop needed:

| N | W | Average jump (125, standard drives) | Hyperdrive only (100) | Scram drive (150) | Jump drive (200) |
|---|---|---|---|---|---|
| 4 | 2.206 | 7.53 | 4.82 | 10.85 | 19.3 |
| 5 | 2.416 | 6.28 | 4.02 | 9.05 | 16.1 |
| 6 | 2.604 | 5.41 | 3.46 | 7.79 | 13.8 |
| 7 | 2.776 | 4.76 | 3.05 | 6.85 | 12.2 |
| 8 | 2.962 | 4.18 | 2.67 | 6.02 | 10.7 |
| 9 | 3.104 | 3.81 | 2.44 | 5.48 | 9.7 |

So fuel capacity and ramscoop trade off: more jumps means a better star and less ramscoop needed.
A simple reachability calculation over the hyperlane map gives higher W (3.0 at N = 4), so the user's
figures are the conservative choice.

Outside the measured range: below 4 jumps, extrapolate linearly at the average slope (0.18 per jump):
W = 2.026 (3), 1.846 (2), 1.667 (1). Above 9 jumps, use the 9-jump value.

## Cooling

Formulas (`Ship.cpp` per-frame update, `Ship::IdleHeat`, `ShipAttributeCache.cpp`), per frame, with
efficiency e from `cooling inefficiency`:

- `cooling` removes a flat e × cooling heat, at any heat level, and needs no energy.
- `active cooling` removes e × active cooling × (heat / max heat) and spends `cooling energy` × (heat / max heat)
  energy. It works in proportion to how hot the ship is, and stops if the ship runs out of energy.
- `heat dissipation` removes heat × 0.001 × dissipation (also proportional to heat).
- Max heat = 100 × (mass + cargo + `heat capacity`).

At the overheat limit every source is at full strength, so the steady-state "never overheats" test is linear:
heat produced per frame ≤ 0.1 × dissipation × (mass + heat capacity) + e × (cooling + active cooling).
Below the limit, active cooling and dissipation work less, so a ship relying on them sits at a higher idle heat.
Idle heat (from `Ship::IdleHeat`) = max(0, heat generation − e × cooling) / (0.001 × dissipation + e × active cooling / max heat).

`heat capacity` raises max heat. That adds a buffer for bursts and also raises the dissipation at the limit.
Heatsink Partition: +240 for 3 outfit space.

Cooling efficiency e = 2 + 2 / (1 + exp(−x / 2)) − 4 / (1 + exp(−x / 4)), x = total `cooling inefficiency`.
Only Outfits Expansion adds it (1 each), and each also removes 0.0065 heat dissipation:

| Outfits Expansions | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| Efficiency | 100% | 99.6% | 97.2% | 91.8% | 83.7% | 73.9% | 63.5% | 44.1% | 29% |

Cooling outfits: passive (Cooling Ducts, Water Coolant System, Liquid Nitrogen/Helium Cooler, Small/Large/Korath
Heat Shunt, Wanderer Heat Sink, Hai Williwaw Cooling, Visions of Rime, Radiant thrusters and steering);
active (Thermoelectric Cooler, Cooling Module, Ka'het Primary/Support Cooling, Liquid Sodium Cooler,
Quantum Vacuum Battery, Afterburner (Stellar Class)); both (Small/Large Hybrid Cooling, Heirloom Cooling,
Successor Cooling); heat capacity (Heatsink Partition, Liquid Sodium Cooler, Planetary/Stellar Afterburners);
dissipation (Radiative Lamina +0.3).

### Job and outlier scenarios

- **Job scenarios** (what the ship does routinely): checked as steady state at the heat target, with active
  cooling running and drawing its energy. Linear, so the solver handles them directly.
- **Outlier scenarios** (rare events): the ship must survive the exposure without overheating (batteries may
  drain; active cooling stops if energy reaches 0) and then recover while parked doing almost nothing, with
  energy ≥ 0. Not linear: checked by a frame-by-frame simulation of each candidate design, which sends the solver
  back with a tighter constraint when it fails.

Reactor `energy generation` and `heat generation` are constant whether or not the energy is used, so a reactor
added to power cooling adds its full heat all the time.

| Scenario | Type |
|---|---|
| Weapons use (below) | Job |
| Evading (solar rule 3) | Job |
| Staying near a 75th-percentile star (solar rule 2b) | Job |
| Passing a 90th-percentile star at 500–1000 (solar rule 2a) | Outlier |
| Passing through one dark system (solar rule 1) | Outlier |

### Heat target (decided)

Design target: heat at or below 90% of max heat, in every scenario. An overheated ship stays disabled until it
drops below 90%, so 90% is the operational limit.

At 90% heat, active cooling and dissipation run at 90% strength and active cooling draws 90% of its energy, so the
steady-state check stays linear: heat produced ≤ 0.9 × (0.1 × dissipation × (mass + heat capacity) + e × active cooling) + e × cooling.

### Weapons use (decided defaults)

- Combat ships: all weapons firing continuously without running out of energy or exceeding the heat target.
- Non-combat ships, and fighters: about 50% of weapons firing continuously, and all weapons for 2.5 seconds.
- "50% of weapons" means half the total weapon energy and heat draw, not half the weapon count.
- The 2.5-second burst is at normal speed (150 frames), starting from the 50% steady state. It is checked
  conservatively as sums: batteries cover the extra energy and the heat headroom up to 90% absorbs the extra heat.
- Drones follow the fighter rules.
- Combat vs non-combat comes from the role; hull category only matters for fighters and drones.

## Torch engines and injectors

Game rules (`Ship.cpp` movement step, `Ship::Drag`, `ShipAttributeCache.cpp`):

- **Thrusting costs are paid per frame**, including `thrusting fuel`. If a cost can't be fully paid, thrust is
  scaled down by the fraction that can (`FractionalUsage`). A torch with no fuel produces no thrust.
- **`drag reduction`**: effective drag = drag / (1 + total drag reduction), capped at the ship's inertial mass.
  Max speed = thrust × (1 + drag reduction) / drag, so drag reduction multiplies top speed. It is additive across
  outfits (two Sparks give drag / 3), and it is not linear in the solver; small integer sums are enumerated.
- **Afterburner** fires on the afterburner command (and when thrust is commanded but main thrust can't fire),
  adds its thrust on top of main thrust, and only fires if its full cost (energy, fuel, …) can be paid that frame.
- **`magnetic nozzle`** is a slot attribute (generic fit rule): torches provide it, the Remass Injector uses 1.

Avgi fusion torches (the Spark, Zap and Arc list the Avgi Torch licence; see Licences below):

| Outfit | Space | Mass | Thrust | Thrust energy | Thrust heat | Thrust fuel (per s) | Drag reduction | Nozzles |
|---|---|---|---|---|---|---|---|---|
| Z-333 "Spark" | 33 | 333 | 120 | 9 | 60 | 9 | 1 | 3 |
| Z-666 "Zap" | 66 | 666 | 270 | 18 | 120 | 18 | 2 | 6 |
| Z-999 "Arc" | 99 | 999 | 450 | 27 | 180 | 27 | 3 | 9 |
| Z-3600 "Beam" | 360 | 3600 | 600 | 15 | 90 | 18 | 9 | 18 |

(The Beam also gives 6000 turn.) Mass is 10× outfit space, so torches trade acceleration for top speed.

Remass Injector: 6 space, 1 nozzle; +90 afterburner thrust, 3 energy, **−18 heat** (cools while firing),
0.6 fuel per frame (36 per second).

Not special: the Gegno RG3/RG15/RG18 Torch Thrusters and Steering are ordinary engines (more heat, less energy).
The Ion Torch is a mining tool in a gun port that also needs a `drill spar`; it gives 6.9 reverse thrust, so it
counts toward reverse-thrust requirements.

### Torches as generators: the Inductive Extractor

Inductive Extractor (1 nozzle, 12 space, 6 engine capacity): +1.5 energy and +1.5 heat constantly; −30 thrust,
**−24 thrusting energy** (thrusting produces 24 energy per frame) and +6 thrusting heat. A torch ship's energy,
fuel and heat therefore depend on how much of the time it thrusts. Allowed by the fit rule because thrusting
energy may go negative; `thrust` may not, so extractors need enough torch thrust.

Related, to cover later: Avgi R-180/360/720 RCS thrusters have negative turning and reverse-thrusting heat
(they cool, reportedly only when the ship has heat to spare); the Ultraviolet Excimer Laser turret uses 2 nozzles.

### Afterburner, combat and torch usage (decided)

- **Passing through** a system = stop, then jump. **Operating** in a system = flying around in it.
- **Afterburners** are optional and used only in combat situations: combat ships about 10% of combat time
  (positioning, chasing); non-combat ships about 12 seconds to escape.
- **Combat length:** escorts/guards about 90 s; dedicated fighting ships about 4 minutes.
- **Torch engines** are player-controlled and thrust more than most ships: assume 85% of the time, in combat and
  when operating in a system. Energy is the average over that share, with batteries covering the gaps
  (default longest gap 5 s, adjustable). Torch ships need ramscoops and extra fuel capacity to compensate
  (ramscoop rule 3).
- Fuel check for a fight: fuel capacity ≥ one jump's reserve + thrusting and afterburner fuel for the fight
  − ramscoop recovery during the fight (at the combat solar/wind conditions).

Example: one Spark at 85% burns 7.65 fuel/s; one Remass Injector at 10% adds 3.6 fuel/s. A 90 s escort fight
needs about 1,010 fuel, a 4-minute fight about 2,700, plus the jump reserve. A stock Diaspersi (2,400 fuel)
covers the escort fight but not the 4-minute one without extra tanks or ramscoops.

## Shield cortexes

Game rules (`DamageProfile.cpp`, `Entity.cpp`, `MINIMUM_OVERRIDES`): shield damage taken = damage / (1 + total
`shield protection`). Shield protection may not go below −0.99, so the fit rule refuses anything past that.

| Outfit | Space | Shield gen | Shield energy | Shield protection | Connection points |
|---|---|---|---|---|---|
| "Byiaa" Shield Cortex | 13 | 1.9 | 2.53 | −0.33 | +1 |
| "Ej" Shield Cortex | 21 | 3.0 | 4.0 | −0.33 | +1 |
| "Jaase" Shield Cortex | 30 | 4.8 | 6.4 | −0.33 | +1 |
| "Jorv" Shield Cortex | 55 | 10.5 | 14.0 | −0.33 | +1 |
| Shield Cortex Interface | 3 | | | +0.33 | −2 |

Each Interface needs two cortexes' connection points, so n cortexes allow floor(n / 2) Interfaces and the best
total is −0.33 × ceil(n / 2):

| Cortexes | 1 | 2 | 3 | 4 | 5–6 | 7+ |
|---|---|---|---|---|---|---|
| Shield damage taken | ×1.49 | ×1.49 | ×2.94 | ×2.94 | ×100 | not installable |

Other negative shield protection: Crimson Halo (−0.5), "Jiita" Heirloom Shielding (−0.33).

Valuation: shields and shield regeneration are counted as effective values, multiplied by (1 + shield protection),
so the trade-off between more regeneration and weaker shields is scored directly. Protection only takes a few
discrete values, so each is enumerated.

Related: Successor "Inductive" engines (Niis, Aqra, Chyyra, Veusa) pay their afterburner cost in shields, and an
afterburner only fires when its full cost can be paid.

## Multimodal armor

11 Successor hulls have one `multimodal armor` slot; each configuration uses it (generic fit rule), so a ship
carries at most one. All take no space or mass and are unplunderable. Formulas: hull damage taken is divided by
(1 + `hull protection`); movement uses mass / (1 + `inertia reduction`), which speeds acceleration and turning but
not top speed; hull repair is multiplied by (1 + `hull repair multiplier`).

| Configuration | Effect | Cost |
|---|---|---|
| Heavy | Hull damage ÷ 1.2 | 0 |
| Light | Hull damage ÷ 1.1; acceleration and turning ×1.15 | 0 |
| Regen | Hull repair ×1.75 (only useful with hull repair) | 0 |
| Keystone | `quantum keystone` (passage through unstable wormholes); scan interference 3 (outfit scans succeed 25% of the time) | 10,000,000 |
| Resilient | Slowing and corrosion protection 0.5 (in `_deprecated`) | 0 |

The effects multiply other stats, so each configuration is tried in turn; with one slot that is cheap.
The Keystone's wormhole ability is a capability rather than a stat, and its scan interference only matters to a
disguise plan for illegal outfits or contraband.

## Deprecated outfits (decided)

Everything under `data/_deprecated` is excluded by default. Players may still own those outfits from older saves,
so they can be switched back on through the "outfits in play" selection. The Multimodal Keystone is deferred.

## Costs that need heat or other resources present

`ResourceLevels::FractionalUsage` / `CanExpend`: a negative heat cost (cooling while thrusting, turning, firing,
afterburning) can only be paid if the ship currently has at least that much heat. Thrust, reverse thrust and
turning scale down by the fraction that can be paid; an afterburner fires only if its whole cost can be paid.
So the Avgi R-180/360/720 RCS thrusters (negative turning and reverse heat), the Vapor Nuclear Rocket (−6
thrusting heat) and the Remass Injector (−18 afterburner heat) lose effect on a very cold ship.
Check: idle heat ≥ the net negative heat cost of each movement mode.

## Special weapons

Weapon value generally has to include submunitions (damage per projectile × count, recursively) and damage dropoff.

| Weapon | Mechanics |
|---|---|
| Blue / Green Optical Laser + Optical Lasing Generator | `lasing power` slots: the Generator (30 space) gives 3; Blue uses 2, Green uses 1 (generic fit rule). Blue damage falls linearly from full at 0 to 0 at 1500 (`damage dropoff` 0 1500, modifier 0). Green is an anti-missile turret with long range. |
| Grab-Strike Turret, Korath Grab-Strike | Slow homing projectile, reload 20 frames, 60 energy and 150 heat per shot, 108 shield / 32 hull damage, **hit force −240** (pulls the target toward the firer). Adds 100 energy capacity. |
| Cluster Mine Layer | Ammo uses `minelayer capacity` slots (Layer 41, Rack +20, each mine −1). Fires a carrier that splits into 11 stationary "Korath Mine Submunition" mines; the damage is in the mines. Reload 180 frames. |
| Heliarch Attractor | Every frame: 5.4 shield / 4.2 hull damage, **hit force −45** (pulls the target) and firing force −45 (pulls the firer toward the target). Designed to keep targets from stopping to jump. |
| Ultraviolet Excimer Laser | Uses 2 `magnetic nozzle` slots (needs a torch) and adds 24 thrusting heat. Every frame: 24 energy, 60 heat and **0.24 fuel** (14.4 fuel/s); 24 shield / 18 hull / 18 heat damage, falling to 0 at 2100. |

### What makes these weapons special (decided)

- **Optical lasers** move cost from weapon capacity to general outfit space: the turret is small, the Lasing
  Generator is not a weapon. A weapon-capacity-limited hull can carry more firepower this way. The generic
  capacity constraints capture it; no special rule.
- **Pull weapons** (Grab-Strike, Heliarch Attractor) pull the enemy toward you; most weapons push enemies away,
  some very hard. Enough pull stops an enemy escaping by overpowering its engines. Physics (`Ship::ApplyForce`):
  a hit adds hit force / mass to the target's velocity, and thrust adds thrust / mass, so mass cancels:
  the pull holds a target when average pull per frame (hit force × hits per frame, ÷ (1 + target force
  protection)) exceeds the target's thrust (plus afterburner when fleeing). Gravitational weapons instead treat
  every ship as mass 400. Example: Grab-Strike averages 12 per frame, Attractor 45; an Argosy has 38.9 thrust.
  Weapons are tagged push or pull by the sign of their hit force.
- **Mine layer** fits an unusual combat role: present in combat zones without fighting directly. It can cover a
  retreat, mostly effective against small attackers.

### Range (decided rule, thresholds proposed)

Weapon range (`Weapon::Range`): range override if set, else (velocity override or velocity) × total lifetime,
where total lifetime adds the longest submunition chain.

Rule from play experience: small, nimble ships use close-range weapons and prefer guns (fixed mounts); medium
ships use mid-range weapons; large, low delta-v ships use long-range weapons and strongly prefer turrets.

The game's own stock designs follow it (720 armed stock ships, fighters and drones excluded, split into thirds by mass):

| Size third | Median mass | Acceleration | Turn | Damage-weighted range | Turret share |
|---|---|---|---|---|---|
| Small | 484 | 328 | 135 | 490 | 0% |
| Medium | 1,139 | 182 | 94 | 801 | 33% |
| Large | 2,895 | 132 | 61 | 1,398 | 71% |

Offensive weapon range deciles (189 weapons): 310, 420, 480, 540, 630, 900, 1440, 2560, 5040.

### Weapon energy and heat (decided)

Energy and heat must support continuous fire (as already decided per role). Realistic firing shares are about
60% for guns and 85% for turrets, but highly variable, and running out of energy or overheating mid-fight is a
serious failure, so the requirement stays continuous. Fuel-burning weapons are not used so far.

Decisions on range:

- The band comes from the **finished design's** agility (delta-v), not the hull.
- Use smooth curves, not hard gates, and only **one-sided**: a nimble ship taking a long-range turret is fine
  (its power, heat and size costs are already modelled); a low delta-v ship taking short-range guns is the
  problem to penalize.

What stock ships show (714 armed stock ships, damage-weighted geometric-mean range):

| Turn quartile | Median turn | Range p25 / median / p75 | Gun share of damage |
|---|---|---|---|
| 1 | 45 | 576 / 991 / 1756 | 30% |
| 2 | 80 | 540 / 945 / 1816 | 38% |
| 3 | 114 | 405 / 510 / 1247 | 57% |
| 4 | 160 | 442 / 540 / 900 | 80% |

Correlation of log range with acceleration is about 0, with turn −0.09, with mass 0.3: stock designs are noisy,
but low-turn ships clearly avoid short-range weapons and fixed guns.

Range and gun curves (decided, anchors provisional):

- **Agility** combines turn and acceleration as an "equivalent turn": √(turn × acceleration × 94 / 182), using
  displayed values (turn in degrees/s, acceleration as shown in ship info). 94 / 182 is the ratio of the medium
  third's median turn to median acceleration, so a ship with typical proportions gets its own turn rate back.
- **Comfortable range** from agility: none at ≥ 140; ~400 at 110; ~600 at 80; ~900 at ≤ 45 (interpolated).
  A weapon at or above it counts in full; below it, its value is (weapon range / comfortable range)².
  Long range is never penalized.
- **Fixed guns** count in full at agility ≥ ~110 and taper below that. Turrets are never penalized.

## From the earlier spreadsheet project (reviewed)

The user's earlier manual design doc was checked against the game code and data.

### Corrections to the old doc

- Shield cortex penalty applies **at all times**, not only while shields charge, and is damage / (1 − 0.33):
  +49% for one cortex, ×2.94 for two without an Interface. The old policy (at most 2 cortexes, and an Interface
  if 2) stands and matches the sweet spot found above; it covers Jaase and Jorv too, not only Byiaa and Ej.
- Overheating damages hull only on ships with `overheat damage rate` (21 special hulls such as Avgi windjammers
  and aberrants, plus the Lantern Fission Core and Vapor Nuclear Rocket). Other ships just shut down until they
  cool below 90%.
- Ion damage drains energy only (`Entity::DoStatusEffects`); without energy, shields stop regenerating but do not
  drain. Discharge is the damage type that drains shields.
- Anti-missile weapons target projectiles with `missile strength`, not homing projectiles as such: 9 homing
  weapons can't be shot down and 10 non-homing ones can.
- Shield Refactor Module: ×1.2 shield generation and shield energy, −0.25 hull repair rate, **and −20% hull
  repair multiplier**; its extra heat is a flat +0.32 shield heat, not a multiplier.

Confirmed from the old doc: no outfit raises max shields or hull; Ka'het Compact Engine and Sustainer Nacelles draw
energy constantly (`energy consumption`); 18 of 21 dedicated reverse thrusters use weapon capacity; every weapon
uses exactly one gun port or one turret mount, and all anti-missile weapons are turrets; heat, ion, slowing and
scrambling damage is 50% blocked by shields, disruption is 50% blocked by their absence; an overheated ship can't be
boarded (boarding needs low hull or no crew); one Optical Lasing Generator supports three Green Optical Lasers.

### Decisions

- **Drives:** unless the role says otherwise, every design has hyperdrive, jump drive and quantum keystone
  capability, as stats: `hyperdrive` (Hyperdrive, Scram Drive, Fusion Drive), `jump drive` (Jump Drive, Point
  Drive), `quantum keystone` (Quantum Keystone and Quantum Key Stone at 1 space, Harmonic Keystone, the
  Multimodal Armor: Keystone, unique items).
- **Ramscoop:** the old "1000 fuel and ramscoop 6" target was a manual rule of thumb; the refuel-time rule above
  replaces it. Kept here for reference only.
- **Afterburners:** the player-flown hero ship gets no afterburner by default (input device). Fleet ships may
  have them, but the AI uses them liberally and then waits on ramscoops to refuel, so fleet ships with
  afterburners need ramscoop recovery (ramscoop rule 3). Roles therefore say whether a ship is the hero ship
  or a fleet ship.

### Rules adopted from the old doc

1. **Anti-missile:** most ships need at least one anti-missile turret. Exceptions: small fighters (or similarly
   small, nimble combat ships) that must choose between offence and anti-missile; specialty ships; combat ships in
   a fleet with enough dedicated point-defence ships (not assumed unless stated).
2. **Scanners:** cargo, outfit and asteroid scanning are worth nothing unless the role asks for them (looting,
   specific missions, mining). Tactical scanning is of minor value.
3. **Jamming:** radar and optical jamming count as missile defence. Scan interference counts only for roles
   carrying illegal goods. Cargo scan opacity also helps freighters that expect pirates.
4. **Disable vs destroy:** roles choose between capturing and destroying ships. Capture-focused ships want high
   shield damage relative to hull damage, shield disruption, and weapons that stop dealing damage quickly
   (instantaneous hits rather than slow projectiles still in flight). Ion, heat and slowing weapons support
   disabling but can't make a ship boardable on their own. Destroy-focused ships score plain damage.
5. **Fuel generation** is safer than ramscoop (independent of stars) but rarely worth its space.

### Average fuel per jump (decided)

With both a hyperdrive and a jump drive, route-finding picks the route that uses the least fuel; in play that
averages about one jump drive jump for every three hyperdrive jumps (an average, not a fixed sequence). So
average fuel per jump = 0.75 × hyperdrive fuel + 0.25 × jump drive fuel, using the drives actually fitted
(125 with the standard Hyperdrive and Jump Drive; 157.5 with a Scram Drive and a Point Drive).
This is where the old spreadsheet's `ROUNDUP(jumps × 1.25) × 100` came from.

- "Jumps of fuel" (N in the ramscoop wind table) = fuel capacity / average fuel per jump. 1000 fuel = 8 jumps.
- The ramscoop refuel rule refills one average jump in about 2 s of fast-forward (decided); see the table above.

### Damage weighting (decided)

Weapon damage is scored as a weighted mix of shield and hull damage, by role goal (from the old spreadsheet's
"Weighted DPS" columns, recovered from its values):

| Goal | Shield damage | Hull damage |
|---|---|---|
| Normal combat | 60% | 40% |
| Disable: general disabling, looting, boarding or capturing, no specific target | 75% | 25% |
| Destroy, or balancing a shield-heavy armament | 30% | 70% |

**Capture-intact:** a specific hull must be captured and must survive being disabled.

- Only instantaneous damage weapons (projectile lifetime of one frame, no submunitions: the hit lands the frame
  it is fired and damage stops the moment firing stops). Anti-missile and tractor beams are unaffected.
- If any available outfit deals shield disruption, the ship must be able to disable the target while the
  target still has at least 50% shields (see "Capture-intact: the 50% shields test" below), and its
  instantaneous weapons are scored with the destroy weights (30 / 70).
- Otherwise its instantaneous weapons are scored with the disable weights (75 / 25).

Instantaneous weapons in current data: 82, including every one the old spreadsheet marked. Shield disruption
comes from the Shield Disruptor Turret (instantaneous), the Drak Draining Fields, the Digger mining beams and the
Prototype Fusion Cannon (not instantaneous).

### Output explanation (decided)

Besides the loadout, the tool explains each design: results against each rule, what limited the design (outfit
space, heat, energy, …), and an **all-in cost** per outfit: its own outfit space plus the share of cooling and
generator space its heat and energy imply (from the old spreadsheet's "heat and energy compensated outfit space").
The spreadsheet needed this because cooling and power were chosen last; the solver chooses everything together and
counts heat and energy directly, so the figure is only for explaining results (and possibly for ordering the search).

## Product decisions

- **Standalone tool with its own memory.** The tool keeps its own catalog (outfits, hulls, variants, shops) and
  settings in a per-user folder. Game files are only read by `import`, which updates the catalog and reports
  what was added, removed or changed. No game data is shipped in the repository; a first-run import is required.
- **Allowed by default, with a blocklist.** Users of this tool have large outfit choices and are after optimal
  ships, not merely workable ones, so more outfits are available to them (by buying or farming) than not.
  Everything is available unless blocked by name, hull or category. Deprecated outfits and hulls are blocked
  by default. Blocks persist between runs.
- **Budgets are ignored.** Cost is reported but never limits a design.
- **Licence:** Zero-Clause BSD, with an overstated notice that the repository is AI-generated and should be
  assumed not to be protected by copyright (NOTICE.md).

## Licences (decided)

The backend ignores licence requirements entirely. Licences are an availability question: blocking a licence
(`block --license "Avgi Torch"`, or answering no in `setup`) means the player doesn't have it, which also covers
outfits added by later imports. Front-end presets can build on this.

Revised (user): a licence only limits buying. An outfit that needs a blocked licence is still available if it can
be plundered from an allowed source (plundered outfits need no licence); a hull that needs one is still available
if ships of it can be captured (not uncapturable, can be disabled, has a sprite, from an allowed source).

## Stats whose missing value is not 0 (for pruning)

Most attributes behave as 0 when absent, but some have defaults or are not monotonic, so obsolescence pruning
needs an explicit "value when missing" and direction per stat. Found in the game code so far:

- `jump range` on a jump drive: missing means the default range, 100 (`System::DEFAULT_NEIGHBOR_DISTANCE`).
  A listed value can be worse than missing (the Asteroid Jump Drive (Patir 18) lists 48).
- `missile strength` on a weapon's projectile: 0 or missing means it **can't be shot down** at all (best for the
  attacker); any positive value makes it a target for anti-missile, and higher values survive better. Not
  monotonic: treat "0" and "> 0" as different kinds.
- Weapon `reload`, `burst reload`, `burst count`: missing means 1.
- `turret turn` on a turret: missing means the legacy default of 4 (with a warning).
- `hyperdrive fuel` / `jump drive fuel`: missing means 100 / 200 (150 for a scram drive); the importer fills these in.
- Hull `threshold percentage` and `absolute threshold`: missing means the default disable-threshold formula.

Pruning treats any stat not in its direction table as "must be equal", so an unlisted case can't prune wrongly.

## Capture-intact: the 50% shields test (decided)

Goal in play: the target is disabled (hull below its disable threshold) while it still has at least 50% of its
shields. The Prototype Fusion Cannon is not instantaneous, so it is excluded like any other slow weapon.

Assumptions: 80% of the damage on the target comes from capture-intact ships, 20% from stock ships not under
the player's direct control (allies, passers-by). Stock damage is 53% shield / 47% hull, the average over all
stock loadouts, with no piercing. Disruption is counted from this ship alone, the worst case. Target
regeneration is ignored, so the test does not depend on fleet size.

Test, per target: time for its hull to fall from full to the disable threshold, against time for its shields to
fall to 50%. Disable threshold (`Ship::FinishLoading`): `absolute threshold` if set, else hull × `threshold
percentage` if set, else hull × (0.1 × (1 − t) + 0.5 × t) with t = 1 / (1 + 0.0005 × hull), plus `hull threshold`.

Default targets: the 48 hulls from Pug, Korath, Heliarch, Ka'het and Quarg (by data folder or name) that no
shipyard sells, have shields, and are not fighters, drones, scenery (asteroids, game mechanics, unclassified)
or "Aberrant" wrecks. A role can name its own targets instead.

Finding: this is hard. A weapon's own shield damage works against the goal, and the Shield Disruptor Turret deals
228 shield damage per second. On an Argosy, 2 Shield Disruptor Turrets and 4 Heavy Lasers leave a Palavret at
24% shields and pass for 3 of 48 targets; piercing (Pug and LG Gridfire Turrets 30%, pulse lasers 5%) helps.

Mechanics (`DamageProfile.cpp`, `Entity::DoStatusEffects`): disruption builds a level on the target that decays by
1% per frame, so steady fire of r per frame holds the level at about 99 × r. While shields are up, a hit's shield
damage is multiplied by s = (1 − piercing) / (1 + 0.01 × level) and its hull damage by 1 − s. Examples, one weapon on one target:

| Weapon | Disruption / s | Steady level | Damage reaching hull through shields |
|---|---|---|---|
| Shield Disruptor Turret | 14.4 | 24 | 19% |
| Drak Draining Field | 60 | 99 | 50% |
| Digger Mining Turret | 4.8 | 8 | 7% |

## Workflow and "can't be done" results (decided)

- Input: one hull (later possibly a shortlist of hulls; TODO) plus the roles. The tool optimizes that hull for the
  stated goal; it does not pick the hull.
- "This hull can't do this role" is a valid, sometimes expected, result. Some roles suit few hulls: capture-intact
  suits fewer than about 10% of hulls.
- An infeasible result still reports:
  - which hard requirements can't be met together, and the limit behind each (outfit space, a mount type, heat,
    energy, what is available);
  - the closest design found and how close it gets (for example "Palavret disabled at 35% shields, target 50%");
  - which single relaxation would make it feasible, where the solver can find one (unblock an outfit, drop a
    requirement, accept a lower target).
- With a shortlist, each hull gets its own result, ranked, with infeasible hulls listed last with their reasons.

## Role sections: should / must / may (decided)

How a design request is thought about (user's framework, adopted for role files):

- **should**: the general baseline of what to optimize and how.
- **must**: must-have stats (hard requirements), or values to weigh much more heavily than the should section
  would suggest (`emphasize`).
- **may**: values the should section would give little or no weight, now given some real weight but never top
  priority (`bonus`).

- **must not**: the ship must not have it (the stat must be 0); also switches off a default requirement for it,
  e.g. a peaceful-area freighter that must not have a jump drive or anti-missile.
- **should not**: actively avoided, but accepted if worth enough (negative weight).
- The steps apply in order (should, must, may, should not), each claiming a fixed share of the score and scaling
  what came before: emphasize 50%, may 10%, should not −20% (defaults). Their strength never depends on how
  many items earlier sections have.
- **Maneuverability** means turn and delta-v (turn rate and acceleration); reverse thrust has its own must level.
- **deprioritise** (inside should): the metric's weight is cut to 10%, even when another combined role or a
  composite weights it.

Outfit filtering by tag is separate (`[outfits]`) and only for roles that truly exclude something. Example: the
in-combat scavenger does not forbid damage weapons; its own damage simply gets no weight, since other ships do
the damage.

## Baseline requirements and hull-type exceptions (decided)

Every ship, by default: fits (game rule); can move; hyperdrive, jump drive and quantum keystone; combat energy
balance and heat ≤ 90% with weapons firing (dim star); energy and heat ≤ 90% near a bright star; ramscoop > 0;
at least one anti-missile weapon. Conditional: the 2.5 s burst (non-combat, fighters, drones), heat-gated
movement, fuel for a fight, evading, refuelling for long range, no afterburner on the hero ship, capture-intact.

Exceptions by hull category (automatic, from the hull's `category`, the hull type shown in game):

| Category | Skips | Instead |
|---|---|---|
| Fighter, Drone | drives, ramscoop, anti-missile | non-combat weapon rules (50% continuous + 2.5 s burst) |
| Interceptor | jump drive, ramscoop, anti-missile, combat energy and heat balance | reserves for a 90 s battle at 50% weapons: battery covers the energy drain and heat stays ≤ 90% (from idle heat, exponential approach) |

A role can still require any of these explicitly with `[must]`.

## Magazine weapons (decided)

- Long-range magazine (ammo) weapons are used in the opening part of a fight: the first 50% of an escort fight
  (45 of 90 s) and the first 35% of a dedicated fight (84 of 240 s). After that their use is exceptional:
  the distance has closed and close-range weapons take over.
- "Long range" uses the long band, range above about 1100. Shorter-range ammo weapons (Gatling Gun, Speckle
  Coilgun, …) count over the whole fight.
- **Depth:** ammo carried ≥ continuous fire over the weapon's window × fights between restocks (role setting
  `fights_per_restock`, default 2). Extra storage (Meteor Missile Box, Sidewinder Missile Rack, …) adds capacity
  for ammo at an outfit-space cost; the fit rule enforces capacity.
- **Value:** a long-range magazine weapon's damage counts × its window share (0.5 or 0.35).
- Energy and heat keep the all-weapons-continuously rule.

Built-in magazines last 15–80 s of continuous fire for most launchers (Meteor Missile Launcher 40 s, Sidewinder
Missile Launcher 45 s, Torpedo Launcher 75 s, VLS 27 s); gun-type ammo weapons last 150–270 s.

## Solver, first version

- OR-Tools CP-SAT, one integer count per candidate outfit (available, not filtered by the role, not needing a
  capacity nothing supplies; uncategorized, licence and mineral items excluded).
- Exact linear constraints: the game's fit rule, drives, ramscoop, anti-missile, heat and energy in each job
  scenario at the 90% target (worst of regeneration, thrust and turning via auxiliary variables), burst energy,
  magazine depth, fight fuel (ramscoop recovery ignored: conservative), long-range refuelling, the role's hard
  requirements. Interceptor reserves use a conservative steady-state heat bound.
- Values that depend on the design (mass in acceleration, agility in weapon value, heat dissipation,
  regeneration multipliers) are linearized around the current design by finite differences with the calculator.
  Cooling efficiency is exact (one constraint per inefficiency level). Superseded in part: see "Solver, second
  version" below.
- Each design is re-checked with the calculator. If none passes, the closest design and its failing checks are
  reported.
- Infeasible: each requirement group is switched off in turn; groups whose removal makes a design possible
  are reported as blockers.
- `ammo X 0` on a weapon means it only fires with X installed (Drak weapons need a jump drive) and is handled as
  a required outfit.

## Availability: setup and source rules (decided)

- After the first import, the user goes through what to allow or block, by source group, outfit category and
  licence (`setup`; the GUI will do the same), and can change it later (`block`, `unblock`, `setup`).
- An outfit is obtainable if it is sold in some outfitter, or installed on a ship that can be disabled and
  plundered, from a source group that isn't blocked, and not marked unplunderable.
- Always blocked: unplunderable outfits sold nowhere; outfits found only on person ships or other ships that can
  never be disabled (they can't be boarded, captured or plundered).
- Source groups blocked by default: Drak, Quarg, Vyrmeid, and scripted/test ships ("Rescue Dummy", Game
  Mechanics hulls). Aberrant ships can't be captured but can be plundered, so the Ka'het group stays counted.
  Quarg gear is often the best a player can get, but plundering or capturing Quarg ships has large story and
  gameplay consequences, so it is opt-in.
- Explicit allows and blocks of named outfits win over the source rules.
- Source group = the data folder the ship is defined in. Person entries (`person`) list their ships; `never
  disabled` and `uncapturable` ship flags are now imported.

More source rules (decided):

- A ship without a sprite can't be disabled, captured or plundered, by definition. Variants inherit their model's
  sprite, as in the game.
- The Avgi Windjammer, Bluejacket and Sprout don't count as sources: they can be boarded, but carry nothing of
  value to a design (minerals, and a gun with a 9-hour reload).
- Outfits defined but used nowhere else in the game data are future (or abandoned) content: blocked by default.
  The importer records every name used outside outfit, ship and shop definitions to tell these apart.
- Outfits mentioned only in missions and similar (not sold, on no ship) are usually given once and often taken
  back later in the mission: available, limited to one copy. Mission files don't always have "mission" in their
  name (e.g. `remnant 1 introduction.txt`), so the check uses every non-definition entry, not file names.
- Shop stock added by events counts as sold.
- Hand to Hand gear, licences and minerals get no weight and are never considered or installed. Exception, for
  later: roles that board ships with illegal weapons allowed assume lots of Nerve Gas grenades, one per bunk,
  for the illegal/contraband calculations.
- When the defaults miss something, the user blocks it after seeing a loadout and runs again.

## Survivability is regeneration-based (decided)

Max shields and hull come from the hull alone (no outfit raises them), so survivability scores shield regeneration,
hull repair (both effective, i.e. including protection) and anti-missile, not max shields or hull.

## The user's manual design method (for reference)

1. Optimize the engines within the engine capacity budget (caveat: reverse thrusters mostly use weapon capacity).
2. Optimize the weapons within the weapon capacity budget.
3. Optimize the rest of the ship with the remaining outfit space.
4. Check whether the finished ship is balanced for its role, particularly the ratio of engines to weapons to the
   rest. If not, artificially shrink the weapon budget, the engine budget or both, and go back to step 1.

Different goals can swap steps 1 and 2, or start with scaled-down budgets.

## Solver, second version (trying; revisit if it doesn't work)

The first version followed one chain of linearized solves from one start and got stuck in local optima (an Argosy
warship with no shield regeneration, score 0.548 against its own ideals). Changes, after the user's manual method:

- **Absolute scoring.** Each metric is scored by its place among the stock ships (models and variants as outfitted
  by the game; scripted, deprecated and sprite-less ships left out), counting only ships with a non-zero value:
  piecewise linear through the sorted values, 0 at 0, 1 at the best stock ship, then rising at half the rate
  (`TAIL_SLOPE`). A metric fewer than 5 stock ships have falls back to the best this hull reaches alone. The
  linearized objective uses the secant slope around the current value (±25%, at least the smallest stock value).
- **"Best of" composites.** `survivability` = best of `durable` (shield regen 2, hull repair 1, anti-missile 1)
  and `evasive` (agility 2, top speed 1, anti-missile 1). Every combination of branches is a route; each start
  optimizes one route's weights, and a design's score is its best route. Nothing is decided by hull category.
- **Budgets and starts.** Roles give ranges for the weapons budget (share of the hull's weapon capacity weapons
  may take) and engines budget (same for engine capacity); defaults 0–100% and 40–100%. The dedicated warship
  uses 85–100% (the user's gut says a dedicated combat ship never goes below 95%; trying 85%), the escort
  60–100%. Starts: every route × weapons budgets × engines budgets (three points per range, two if the range is
  20% or narrower). The steps of the manual method are solved together within the budgets rather than one after
  another.
- **Trust region ("bands").** Each start linearizes at the hull's stock design (else a feasible design). After the
  first step, the next design's mass must stay within ±50% of the current one; the band widens ×1.5 after a step
  that improves the route's exact score and halves otherwise, stopping below 5% or after 4 accepted steps. Mass is
  the main non-linear driver (acceleration, turn, agility, weapon factors); agility and protection get no band
  of their own yet.
- **Linearization misses.** A design that fails a calculator check is usually a linearization miss (for example,
  heat sinks raise heat dissipation, which the model held at the old value), so the model is linearized again at
  the failing design; only a design that comes back twice is excluded with a no-good cut.
- **Polish.** Every start's best design is polished with the calculator alone: the best single add, remove or
  swap (one out, one or two in) that keeps every check passing, repeated until nothing improves (time shared,
  default 60 s). Polish ignores the budgets, which are a search device, not a rule. The best polished design wins.
- **Output.** Balance ratios (weapon and engine capacity used; outfit space split between engines, weapons, the
  rest and free), each metric's place among stock ships, every route's score, and every start's result.

First result, Argosy as a dedicated warship: 0.712 (weapon value beats 504 of 731 stock ships, agility 586 of
834), in about 3.5 minutes. Polish lifted every start, by up to 0.2. Seen so far: adding percentiles rewards
specialization. An earlier run turned extremely well (beats 822 of 834) and accelerated badly (beats 12), because
`maneuverability` adds turn and acceleration. Combining them as agility (a geometric mean) would reward balance
instead.

### Follow-ups (decided)

- **Unique outfits are for hero ships by default.** Outfits with the `unique` attribute or in the Unique category
  (story items such as the Shield Beetle Pendant) are left out unless the request is for a hero ship; a role can
  set `unique_outfits` either way.
- **Balance by multiplying.** Composites can be `combine = "product"`: the parts' stock-ship scores are multiplied
  as a weighted geometric mean, with the weights as exponents (the adjustable weighing factor).
  `maneuverability` = turn rate × acceleration, 1 to 1 for now. For the linearization, a part's score is floored
  at 0.02 so a zero part still has a finite slope. Result: the Argosy warship's turn and acceleration beat 408
  and 563 of 834 stock ships (before: 822 and 12), score 0.729.
- **Noted, may revisit:** run time (about 4 minutes per hull) and the order of the manual method's steps (solved
  together within the budgets).
- **No outfits that do nothing; space-efficient choices (user review).** The Argosy design above carried 5 Small
  Heat Shunts (heat settled at 5%: 2 were enough) and 3 Outfits Expansions with 28 outfit space unused
  (expansions cost cargo space, cooling efficiency and heat dissipation). The model allowed the leaner design;
  the solver just had no reason to prefer it, because a useless outfit cost almost nothing in the linearized
  objective. Fixes:
  - Tie-break in the objective: −1e-5 per unit of outfit space or cargo space an outfit uses up
    (`WASTE_PENALTY`), so between otherwise equal designs the leaner one wins. This also gives the user's passive
    cooling ladder (Cooling Ducts 5/300, Small Heat Shunt 7/810, Wanderer Heat Sink 12/1140, Large Heat Shunt
    24/3240: Large Heat Shunts first, then small ones) without a hard-coded table.
  - Polish first strips any outfit whose removal doesn't lower the score, then also tries group swaps (several
    of one outfit out, one or two of a substitute in, a substitute providing something the removed one
    provides), and accepts a move that keeps the score while using less space. Only the best 4 starting designs
    are polished, with more time each.
  - Result: 0.755, no heat shunts, 4 expansions all needed (11 space left, one fewer wouldn't fit). Polishing
    the old flawed design removes all 5 shunts and all 3 expansions (0.729 → 0.748).

## Energy per shot and regeneration (decided, from in-game testing)

- **Energy per shot.** The game warns "insufficient energy to fire?" (`Ship::FlightCheck`) when a weapon's firing
  energy per shot is more than the energy capacity plus one frame of net generation (energy generation − energy
  consumption + fuel energy + solar collection). Without a battery, that one frame ("surge" in the ship info) is all
  there is, and a weapon that needs more never fires: the Argosy design above had no battery, and its Drag Cannons
  (and its Wanderer Anti-Missile) never fired until a Supercapacitor was added. Now a hard check and a solver
  constraint for every fitted weapon. Solar counts at combat strength (the game counts it at full strength), to be
  safe at a dim star.
- **Regeneration.** A design with no shield generation and no hull repair at all is invalid by default (shield or
  hull regeneration above 0 passes). `[ship] needs_regen = false` turns it off.
- **Game version.** The user plays 0.11.2. The catalog had been imported from the development version (after
  0.11.3): 32 outfits changed, 18 new, 2 hulls changed. Import from the installed game's data to match it.

## Fire-rate penalty for combat roles (decided)

In combat roles (`combat = true`), a weapon firing fewer than 6 shots per second (per copy, bursts averaged in)
keeps value × (shots per second / 6) ^ 1.07 of its damage value: about 20% at 1.33 shots per second (the user's
figure, from play; a squared ramp kept only 5%), 31% at 2, 48% at 3, 82% at 5. It applies to damage (shield and
hull) in `weapon value` only. Utility (anti-missile, tractor, push and pull, disruption) is not affected, and the
raw `shield dps` and `hull dps` metrics stay raw. Constants: `COMBAT_MIN_SHOTS`, `COMBAT_RATE_EXPONENT`.

## Parallel runs (decided: works in a small container, tuned for a Ryzen 9 3900X)

- Starting designs are independent, so they run side by side in worker processes (`spawn`, the same on Linux,
  Windows and macOS). Each start keeps its own no-good cuts. The polish of the best designs also runs side by
  side; with more jobs, more designs are polished (at least 4, else one per job), in waves sharing `--polish`.
- Defaults come from the CPUs the process may use (affinity and container limits where the OS reports them): two
  CP-SAT threads per job, as many jobs as fit, at most one per start. Ryzen 9 3900X (24 threads): 12 starts at
  once, 2 threads each. 4-CPU container: 2 jobs × 2 threads. The sequential solves before the starts use every
  CPU (at most 16 threads). `--jobs` and `--threads` override; `--jobs 1` runs everything in one process.
- Time is mostly set by the solve and polish time limits, so a faster CPU mostly buys a better search; more
  cores buy shorter runs. A GPU isn't used (CP-SAT and the calculator run on the CPU only).
- Measured in the 4-CPU container, Argosy warship: about 230 s in one process, 135 s with 2 jobs. On a 3900X, the
  12 starts take about as long as one wave of starts, so expect well under a minute plus the polish (60 s
  default).

## Governments you won't attack (decided)

Plundering a ship means attacking it, which ruins relations with the government flying it, and some races have
several governments (Kor Efret, Kor Mereti, Kor Sestor; Gegno Vi and Gegno Scin). So availability also goes by
government, on top of source groups:

- Import records each government's display name and the ships it flies: fleet variants, and mission NPCs (their
  own ships, inline fleets and fleets they name). Persons are unplunderable already.
- A plundered outfit counts if its ship comes from an allowed source group and either no government flies it (no
  relations to damage, so it counts: the user's rule; sprite, never-disabled and person rules still apply) or at
  least one government flying it is one the player will attack. The same goes for capturing a hull that needs a
  licence the player doesn't have.
- Each government is its own choice. Not grouped by race or display name (user correction): "Korath" starts at
  total war with the player, "Korath (Civilian)" at peace, and attacking the civilians would rarely make sense.
- Defaults from the name: "(Civilian)" governments are spared, "(Hostile)" ones attacked; a government with a
  "(Civilian)" twin is attacked (Korath), one with a "(Hostile)" twin spared (Merchant, Kor Mereti, Syndicate,
  People's Houses, Drak); everything else attacked. Settings keep explicit choices both ways
  (`blocked governments`, `allowed governments`), so defaults only apply to governments never answered. Literal
  match only: "Hai (Unfettered Civilians)" is not "(Civilian)".
- `setup` step 4 asks only about governments that are a plunder source of something the player can't simply buy
  (not sold, or sold but needing a licence they lack), from allowed source groups, ordered by how many outfits come
  only from them. Outfits also on a ship no government flies are left out of the counts (obtainable whatever
  the answer). With the user's 0.11.2 settings: 36 questions (13 with outfits only from them). `block --government NAME` / `unblock` take an exact government name; `sources` lists
  them with their state.
- Catalog version 4: run `import` again.
- **Source groups are now a hidden, advanced gate** (user): with governments deciding plunder, no source group
  except "scripted" would normally be refused. Only "scripted" is blocked by default; `setup` step 1 shows the
  refused groups and asks whether to review them (default no). The old Drak, Quarg and Vyrmeid source defaults
  became government defaults: a government flying only ships from those folders, or named after those races, is
  spared, after the name rules ("Drak (Hostile)" is still attacked). Settings saved earlier keep their source
  blocks until changed.

## Ten-run comparison (user, 0.11.2, Ryzen 9 3900X) and fixes

Ten Argosy warship runs: scores 0.765–0.788 (mean 0.778), 36–81 s each, all on the evasive route, two design
families (Z-333 torch with an Inductive Extractor, top speed 1459; or reactors and Outfits Expansions). Flaws found:

- Run 5 carried 72 Railgun Slugs and a Slug Rack with no Railgun: ammunition takes no outfit space, so the space
  tie-break didn't see it. The tie-break now also counts one unit per outfit fitted, and polish strips again at
  the end.
- Run 8 carried 4 Outfits Expansions plus 2 Cargo Expansions to pay back the cargo space they cost (Argosy cargo
  can't go negative), with 11 outfit space unused. Removing either alone breaks the fit rule, so single moves
  couldn't fix it; polish now also tries removing two different outfits at once. Re-polished, run 8 goes from
  0.781 to 0.796 with no expansions at all.
- Two runs after the fix (container): 0.788 and 0.793.

## Turret turn, projectile speed, thrust-made power, and a weapons-focus knob (decided)

- **Turret turn:** a turret's damage value × (turret turn °/s ÷ 150) ^ 1, up to 1 (150°/s is about the median
  turret). Guns and homing weapons are unaffected. `TURRET_TURN_FULL`, `TURRET_TURN_EXPONENT`.
- **Projectile speed:** damage value × (projectile speed px/s ÷ 600) ^ 1, up to 1 (600 px/s is about the median).
  Speed, not flight time, so long range isn't penalized. The speed is velocity (or its override), the top speed of
  accelerating projectiles (acceleration ÷ drag), or for weapons whose projectile is a submunition, the
  submunition's. Instantaneous weapons count as infinitely fast: full value. `PROJECTILE_SPEED_FULL`,
  `PROJECTILE_SPEED_EXPONENT`. Both apply in every role; they are about whether shots land, not fire discipline.
- **Power made by thrusting** (Inductive Extractor: −24 thrusting energy) counts only at the torch share × min(1,
  agility ÷ 110): a slow tank can't count on thrusting 85% of a fight. The energy and heat scenarios take the worse
  of the full and reduced shares; the solver uses the agility of its current design.
- **`--emphasize` / `--deprioritize`** on `optimize` and `tools/repeat_optimize.py`: request-level, for one run.
  Emphasized metrics or composites take 50% of the score after the roles are combined; deprioritized ones are cut
  to 10%. `--emphasize firepower --deprioritize survivability` on the warship: weapon value 50% → 83%.
- First runs (Kar Ik Vot 349, container): the Bombardment Turret (360 px/s) gives way to Blue Optical Lasers
  (instantaneous) with Optical Lasing Generators. Default 0.828; weapons focus 0.882 (weapon value 1476 → 2153,
  beats 702 of 712 stock ships).

## Tanks don't chase (decided)

User review (Kar Ik Vot 349): a regeneration tank used ~100% of its engine capacity (engines, torch fuel tanks) but
~45% of its weapon capacity. Maneuverability kept 1/6 of the score on both survivability routes.

- **Route effects.** A best_of branch can say what changes when it wins: `when_chosen = { scale = {...}, bonus =
  {...} }`. `durable` (the tank): maneuverability × 0.25, pull force gets a 5% bonus (pulling enemies in finishes
  fights a slow ship can't chase; long range already counts more on slow ships through the comfortable-range rule).
  Anything explicitly emphasized (a role's `[must] emphasize`, or `--emphasize`) is not cut: the "this tank should
  be able to chase" override, off by default.
- **A floor under mobility.** The cut alone produced a ship turning 2°/s. Roles can now set `[must] min_percentile`:
  a minimum as a share of stock ships with the metric, resolved against the current catalog. The warship: turn rate
  and acceleration at least the 5th percentile (0.11.2: 33°/s, 77).
- **`--emphasize name=share`** gives exactly that share of the score (e.g. `maneuverability=0.2`); a bare name
  shares 50% with the other emphasized names.
- **Balance line:** outfits that supply something only installed weapons use (Optical Lasing Generators' lasing
  power) count as weapons.
- Runs (container): tank default 0.872, turn 40°/s, engines 74% of engine capacity, 6 Blue Optical Lasers;
  `--emphasize maneuverability=0.2`: turn 75°/s, 4 Grab-Strike pull turrets, weapons 75% of weapon capacity.

## Weapon value relative to the average weapon (decided: option A)

Comparing 20 Kar Ik Vot 349 designs with the stock ship: 0.62× the stock's raw damage but 1.57× its weapon value,
2× its shield regen, 6× its hull repair, 25% of outfit space on weapons against the stock's 40%. The discounts
(range, fixed guns on slow ships, fire rate, turret turn, projectile speed, magazine window) multiply, and an
average available weapon kept 17% of its damage at agility 65 but 54% at agility 140: weapons as a whole lost
value against regeneration on slow ships. The user's principle: discounts should rank weapons against each
other, not weapons against the rest of the ship.

- Weapon value = damage × suitability ÷ the average suitability of every damage weapon the player can get
  (`Role.reference_weapons`), on a ship of the hull's stock agility (`Role.stock_agility`). An average weapon
  counts its full damage. The stock ships used for scoring get the same treatment at their own agility.
- First version took the average at the design's own agility: a design could raise its weapon value by making
  itself slower (beams suit any ship fully, so a smaller average meant a bigger multiplier). The Argosy turned
  into a slow tank. Taking the average at the hull's stock agility (a fixed point per hull) fixed it.
- The ranking within weapons is unchanged for now (guns on slow ships still squared); the curve is to be revisited
  after the user's in-game testing. The homing-missile exemptions are a separate, still-open proposal.
- Runs (container): Kar Ik Vot 0.909, weapons 30% of outfit space, 71% of weapon capacity, 4 Grab-Strike pull
  turrets; Argosy back on the evasive route, 0.770, 4 guns, 98% of weapon capacity.
