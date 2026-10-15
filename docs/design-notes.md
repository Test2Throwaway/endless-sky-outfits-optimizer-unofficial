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
