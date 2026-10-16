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
  Run after the availability filter.
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

Fast-forward runs 3 game frames per drawn frame (`main.cpp`), so 2 seconds = 360 frames. Refuelling at the star
(distance factor 2.0): 0.03 × W × 2 × √(ramscoop) × 360 + 360 × `fuel generation` ≥ jump fuel.
Without fuel generation that is √(ramscoop) ≥ jump fuel / (21.6 × W).

W is the best star wind reachable, which improves with the number of jumps N the ship's fuel allows
(user's measurement, used as given):

| N | W | Ramscoop needed, hyperdrive (100 fuel) | Scram drive (150) | Jump drive (200) |
|---|---|---|---|---|
| 4 | 2.206 | 4.40 | 9.91 | 17.6 |
| 5 | 2.416 | 3.67 | 8.26 | 14.7 |
| 6 | 2.604 | 3.16 | 7.11 | 12.6 |
| 7 | 2.776 | 2.78 | 6.26 | 11.1 |
| 8 | 2.962 | 2.44 | 5.50 | 9.77 |
| 9 | 3.104 | 2.22 | 5.00 | 8.89 |

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
