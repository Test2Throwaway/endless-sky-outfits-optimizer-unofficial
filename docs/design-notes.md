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

Avgi fusion torches (need the Avgi Torch license, except the Beam):

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
