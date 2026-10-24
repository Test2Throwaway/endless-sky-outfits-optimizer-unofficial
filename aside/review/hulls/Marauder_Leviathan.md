# Marauder Leviathan

## fight-anchor (optimized)

**Baseline (current numbers)** — score 0.916, route survivability: evasive

weapon capacity 38%, engine capacity 100%, batteries 1 (+2164 energy capacity), secondaries 1, combat heat peak 68%, battery drawdown 57%, agility 96

```
   3 × Concentrating Solar Cell
   2 × Cooling Module
   7 × Deuterium Slush Tank
   1 × Dwarf Core
   1 × Hai Chasm Batteries
   1 × Hyperdrive
   1 × Jump Drive
   1 × Langrage Hyper-Heaver
   3 × Lantern Fission Core
   2 × Large Heat Shunt
   2 × Large Steering Module
   1 × Quantum Key Stone
   5 × Small Heat Shunt
   1 × Small Repair Module
   1 × Stagnation Beam
   1 × Vapor Nuclear Rocket
   1 × Wanderer Anti-Missile
   1 × Wanderer Ramscoop
   1 × Z-666 "Zap" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| jump denial | +0.39 | +0.39 | 1 | beats 67 of 69 stock ships |
| denial range | +0.26 | +0.26 | 0.6 | beats 4 of 20 stock ships |
| agility | +0.13 | +0.13 | 0.962 | beats 121 of 126 stock ships |
| max speed | +0.06 | +0.06 | 2.62 | beats 126 of 126 stock ships |
| anti-missile | +0.06 | +0.06 | 0.803 | beats 58 of 76 stock ships |
| fuel dps | +0.03 | +0.03 | 0 | beats 0 of 7 stock ships |
| slowing dps | +0.03 | +0.03 | 0.167 | beats 0 of 12 stock ships |
| pull force | +0.03 | +0.03 | 0.778 | beats 9 of 12 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Hai Chasm Batteries | one more | -2.88e-05 | fits, but worth less than what it displaces |  |
| generators | Concentrating Solar Cell | one more | -5.77e-06 | fits, but worth less than what it displaces |  |
| coolers | Small Heat Shunt | one more | -4.03e-05 | fits, but worth less than what it displaces |  |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module, Hai Chasm Batteries |
| shield regen | "Jorv" Shield Cortex | forced in | — | can't pass: Recovery: shields and hull, Combat (240 s): energy | Small Repair Module |
| hull repair | Small Repair Module | one more | -3.46e-05 | fits, but worth less than what it displaces |  |
| engines | Large Steering Module | one more | — | can't pass: Fits (game rule) |  |
| guns | Drag Cannon | forced in | 0.0032 | better: the search missed it |  |
| guns | Speckle Coilgun | forced in | — | can't pass: Magazine: Speck Round |  |
| turrets | Stagnation Beam | one more | 0.0146 | better: the search missed it |  |
| secondaries | Langrage Hyper-Heaver | one more | -0.000274 | breaks Combat (240 s): energy as is; worth less after making room |  |
| anti-missile | Wanderer Anti-Missile | one more | — | can't pass: Combat (240 s): energy |  |
| utility weapons | Horizon Grappler | forced in | — | can't pass: Combat (240 s): energy |  |
| utility weapons | Tractor Beam | forced in | -0.000239 | breaks Combat (240 s): energy as is; worth less after making room |  |
| expansions | Cargo Expansion | forced in | -2.88e-05 | fits, but worth less than what it displaces |  |
| expansions | Outfits Expansion | forced in | -4.61e-05 | breaks Near a bright star (rule 2b): energy as is; worth less after making room | Small Heat Shunt |

## missile-boat (optimized)

**Baseline (current numbers)** — score 0.857, route survivability: evasive

weapon capacity 81%, engine capacity 99%, batteries 0 (+150 energy capacity), secondaries 4, combat heat peak 74%, battery drawdown 0%, agility 95

```
   1 × "Bondir" Atomic Steering
   7 × Anomalous Mass
   2 × Bullfrog Anti-Missile
 168 × Cluster Mine
   3 × Cluster Mine Layer
   3 × Cluster Mine Rack
   1 × Cooling Module
   2 × Deuterium Slush Tank
   1 × Emergency Ramscoop
   1 × Fuel Module
   1 × Hyperdrive
   1 × Jump Drive
   2 × Ka'het Annihilator Turret
   1 × Large Reactor Module
   1 × Quantum Key Stone
   1 × Small Heat Shunt
   1 × Small Repair Module
   1 × Star Tail
  56 × Star Tail Cell
   2 × Star Tail Storage
   1 × Type 1 Radiant Steering
   2 × Vapor Nuclear Rocket
   1 × Wanderer Heat Sink
   1 × Z-333 "Spark" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| weapon value | +0.75 | +0.75 | 0.797 | beats 98 of 124 stock ships |
| agility | +0.12 | +0.12 | 0.96 | beats 121 of 126 stock ships |
| max speed | +0.06 | +0.06 | 1.56 | beats 126 of 126 stock ships |
| anti-missile | +0.06 | +0.06 | 0.671 | beats 48 of 76 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Crystal Capacitor | forced in | -0.000168 | fits, but worth less than what it displaces |  |
| batteries | Large Battery Module | forced in | -0.000261 | fits, but worth less than what it displaces |  |
| generators | Large Reactor Module | one more | -0.419 | no room as is (fit), worth less than what it displaces | Deuterium Slush Tank, Z-333 "Spark" Fusion Torch, Fuel Module, Anomalous Mass, "Bondir" Atomic Steering |
| coolers | Cooling Module | one more | 1.83e-05 | better: the search missed it | Wanderer Heat Sink |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module |
| shield regen | "Jorv" Shield Cortex | forced in | — | can't pass: Combat (240 s): energy | Small Repair Module, Vapor Nuclear Rocket |
| hull repair | Small Repair Module | one more | -7.54e-05 | fits, but worth less than what it displaces |  |
| engines | Vapor Nuclear Rocket | one more | -0.0887 | no room as is (fit), worth less than what it displaces | Deuterium Slush Tank, Z-333 "Spark" Fusion Torch, Fuel Module, Small Heat Shunt, Wanderer Heat Sink |
| guns | Drag Cannon | forced in | — | can't pass: Fits (game rule) | Bullfrog Anti-Missile |
| guns | Speckle Coilgun | forced in | — | can't pass: Fits (game rule), Magazine: Speck Round | Ka'het Annihilator Turret |
| turrets | Ka'het Annihilator Turret | one more | — | can't pass: Must: secondary share ≥ 0.6 | Deuterium Slush Tank, Z-333 "Spark" Fusion Torch, Fuel Module, Bullfrog Anti-Missile, Small Heat Shunt, Wanderer Heat Sink |
| secondaries | Cluster Mine Layer | one more | — | can't pass: Fits (game rule), Magazine: Cluster Mine |  |
| anti-missile | Bullfrog Anti-Missile | one more | -0.245 | no room as is (fit), worth less than what it displaces | Ka'het Annihilator Turret |
| utility weapons | Horizon Grappler | forced in | -0.251 | no room as is (fit), worth less than what it displaces | Ka'het Annihilator Turret |
| utility weapons | Tractor Beam | forced in | -0.251 | no room as is (fit), worth less than what it displaces | Ka'het Annihilator Turret |
| expansions | Cargo Expansion | forced in | -5.98e-05 | fits, but worth less than what it displaces |  |
| expansions | Outfits Expansion | forced in | -5.98e-05 | fits, but worth less than what it displaces |  |

## sniper (optimized)

**Baseline (current numbers)** — score 0.850, route survivability: evasive

weapon capacity 91%, engine capacity 98%, batteries 1 (+3600 energy capacity), secondaries 2, combat heat peak 88%, battery drawdown 94%, agility 102

```
   2 × Anomalous Mass
   3 × Bombardment Turret
   1 × Emergency Ramscoop
   1 × Hyperdrive
   1 × Jump Drive
   1 × Large Reactor Module
   1 × Point Defense Turret
   1 × Quantum Key Stone
   1 × Small Battery Module
   2 × Small Heat Shunt
   1 × Small Reactor Module
   1 × Small Repair Module
   2 × Typhoon Launcher
   5 × Typhoon Storage Tube
 135 × Typhoon Torpedo
   1 × Vareti Engine Block
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| weapon value | +0.60 | +0.60 | 0.848 | beats 105 of 124 stock ships |
| weapon range | +0.20 | +0.20 | 0.772 | beats 95 of 124 stock ships |
| agility | +0.10 | +0.10 | 0.971 | beats 122 of 126 stock ships |
| max speed | +0.05 | +0.05 | 0.975 | beats 122 of 126 stock ships |
| anti-missile | +0.05 | +0.05 | 0.829 | beats 61 of 76 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Small Battery Module | one more | -6.47e-05 | no room as is (fit), worth less than what it displaces |  |
| generators | Small Reactor Module | one more | -0.0498 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| coolers | Small Heat Shunt | one more | -8.62e-05 | no room as is (fit), worth less than what it displaces |  |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module, Bombardment Turret |
| shield regen | "Jorv" Shield Cortex | forced in | — | can't pass: Combat (240 s): energy | Small Reactor Module, Small Repair Module, Bombardment Turret, Small Heat Shunt |
| hull repair | Small Repair Module | one more | -0.0493 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| guns | Bombardment Cannon | forced in | -0.0285 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| guns | "Ojet" Bimodal Coilgun | forced in | -0.0436 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| turrets | Bombardment Turret | one more | — | can't pass: Fits (game rule), Combat (240 s): energy | Small Reactor Module, Small Heat Shunt |
| secondaries | Typhoon Launcher | one more | — | can't pass: Magazine: Typhoon Torpedo | Bombardment Turret |
| anti-missile | Point Defense Turret | one more | -0.0431 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| utility weapons | Horizon Grappler | forced in | -0.0495 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| utility weapons | Tractor Beam | forced in | -0.0495 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| expansions | Cargo Expansion | forced in | -0.0493 | no room as is (fit), worth less than what it displaces | Bombardment Turret |
| expansions | Outfits Expansion | forced in | -3.6e-05 | fits, but worth less than what it displaces |  |

## tank (optimized)

**Baseline (current numbers)** — score 0.823, route survivability: durable

weapon capacity 64%, engine capacity 64%, batteries 0 (+0 energy capacity), secondaries 0, combat heat peak 79%, battery drawdown 0%, agility 75

```
   2 × Anomalous Shield Restorer
   1 × Chameleon Anti-Missile
   1 × Crucible-Class Steering
   1 × Fuel Module
   1 × Gaktem GP Hybrid Steering
   4 × Hai Williwaw Cooling
   3 × Heliarch Attractor
   1 × Hyperdrive
   1 × Jump Drive
   1 × Ka'het Primary Cooling
   1 × Large Heat Shunt
   1 × Magnetic Scoop
   3 × Nanite Enhancer
   1 × Quantum Key Stone
   2 × Small Nanite Fabricator
   1 × Triple Plasma Core
   1 × Z-333 "Spark" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| weapon value | +0.34 | +0.34 | 0.853 | beats 105 of 124 stock ships |
| shield regen | +0.26 | +0.26 | 0.725 | beats 74 of 120 stock ships |
| pull force | +0.15 | +0.15 | 1.25 | beats 12 of 12 stock ships |
| hull repair | +0.13 | +0.13 | 0.77 | beats 34 of 45 stock ships |
| anti-missile | +0.13 | +0.13 | 0.513 | beats 25 of 76 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Crystal Capacitor | forced in | -0.000476 | no room as is (fit), worth less than what it displaces |  |
| batteries | Large Battery Module | forced in | -0.000641 | no room as is (fit), worth less than what it displaces |  |
| generators | Triple Plasma Core | one more | — | can't pass: Fits (game rule) | Heliarch Attractor, Small Nanite Fabricator, Nanite Enhancer |
| coolers | Hai Williwaw Cooling | one more | -0.000366 | no room as is (fit), worth less than what it displaces |  |
| shield regen | Anomalous Shield Restorer | one more | -0.0532 | no room as is (fit), worth less than what it displaces | Heliarch Attractor |
| hull repair | Nanite Enhancer | one more | 0.00051 | better: the search missed it |  |
| engines | Z-333 "Spark" Fusion Torch | one more | — | can't pass: Fuel for a fight | Heliarch Attractor, Anomalous Shield Restorer |
| guns | Drag Cannon | forced in | -0.0197 | no room as is (fit), worth less than what it displaces | Crucible-Class Steering |
| guns | Speckle Coilgun | forced in | — | can't pass: Magazine: Speck Round | Heliarch Attractor |
| turrets | Heliarch Attractor | one more | — | can't pass: Fits (game rule) | Anomalous Shield Restorer, Gaktem GP Hybrid Steering |
| secondaries | Ka'het Emergency Deployer | forced in | — | can't pass: Combat (240 s): heat, Magazine: Ka'het MHD Generator |  |
| secondaries | External Launch Tube | forced in | — | can't pass: Magazine: "Orchid" Nuclear Missile | Heliarch Attractor, Hai Williwaw Cooling |
| anti-missile | Chameleon Anti-Missile | one more | -0.0353 | no room as is (fit), worth less than what it displaces | Heliarch Attractor |
| utility weapons | Horizon Grappler | forced in | -0.0674 | no room as is (fit), worth less than what it displaces | Heliarch Attractor |
| utility weapons | Tractor Beam | forced in | -0.0674 | no room as is (fit), worth less than what it displaces | Heliarch Attractor |
| expansions | Cargo Expansion | forced in | -0.0674 | no room as is (fit), worth less than what it displaces | Heliarch Attractor |
| expansions | Outfits Expansion | forced in | -0.000142 | fits, but worth less than what it displaces |  |

## warship (optimized)

**Baseline (current numbers)** — score 0.963, route survivability: evasive

weapon capacity 65%, engine capacity 89%, batteries 0 (+0 energy capacity), secondaries 0, combat heat peak 85%, battery drawdown 0%, agility 118

```
  20 × Anomalous Mass
   1 × Bullfrog Anti-Missile
   2 × Chameleon Anti-Missile
   3 × Cooling Module
   4 × Deuterium Slush Tank
   1 × Emergency Ramscoop
   1 × Husk-Slice
   1 × Hyperdrive
   1 × Jump Drive
   1 × Liquid Sodium Cooler
   2 × Moonbeam
   1 × Nelmeb GP Hybrid Steering
   1 × Outfits Expansion
   1 × Quantum Key Stone
   1 × Small Repair Module
   1 × Sunbeam
   1 × Triple Plasma Core
   1 × Vapor Nuclear Rocket
   1 × Z-333 "Spark" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| weapon value | +0.50 | +0.50 | 0.936 | beats 116 of 124 stock ships |
| agility | +0.17 | +0.17 | 0.987 | beats 124 of 126 stock ships |
| maneuverability | +0.17 | +0.17 | 0.959 | beats 119 of 126 stock ships; beats 121 of 126 stock ships |
| max speed | +0.08 | +0.08 | 1.21 | beats 126 of 126 stock ships |
| anti-missile | +0.08 | +0.08 | 0.842 | beats 63 of 76 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Crystal Capacitor | forced in | -0.000754 | no room as is (fit), worth less than what it displaces |  |
| batteries | Large Battery Module | forced in | -0.0133 | no room as is (fit), worth less than what it displaces | Chameleon Anti-Missile |
| generators | Triple Plasma Core | one more | -0.538 | no room as is (fit), worth less than what it displaces | Anomalous Mass, Vapor Nuclear Rocket, Husk-Slice, Sunbeam, Moonbeam, Chameleon Anti-Missile |
| coolers | Cooling Module | one more | -0.000674 | no room as is (fit), worth less than what it displaces | Anomalous Mass |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module |
| shield regen | "Jorv" Shield Cortex | forced in | -0.184 | no room as is (fit), worth less than what it displaces | Small Repair Module, Husk-Slice, Sunbeam, Chameleon Anti-Missile |
| hull repair | Small Repair Module | one more | -0.000685 | no room as is (fit), worth less than what it displaces | Anomalous Mass |
| engines | Z-333 "Spark" Fusion Torch | one more | — | can't pass: Fuel for a fight | Deuterium Slush Tank, Outfits Expansion, Anomalous Mass, Vapor Nuclear Rocket, Husk-Slice, Chameleon Anti-Missile |
| guns | Moonbeam | one more | -0.0195 | no room as is (fit), worth less than what it displaces | Cooling Module, Outfits Expansion, Sunbeam |
| turrets | Ultraviolet Excimer Laser | forced in | -0.238 | no room as is (fit), worth less than what it displaces | Cooling Module, Vapor Nuclear Rocket, Husk-Slice, Sunbeam, Moonbeam, Chameleon Anti-Missile |
| turrets | Blue Optical Laser | forced in | — | can't pass: Fits (game rule) | Outfits Expansion, Sunbeam |
| secondaries | Ka'het Emergency Deployer | forced in | — | can't pass: Combat (240 s): heat, Magazine: Ka'het MHD Generator | Cooling Module, Moonbeam |
| secondaries | External Launch Tube | forced in | — | can't pass: Magazine: "Orchid" Nuclear Missile | Cooling Module, Sunbeam |
| anti-missile | Chameleon Anti-Missile | one more | -0.0302 | no room as is (fit), worth less than what it displaces | Vapor Nuclear Rocket |
| utility weapons | Horizon Grappler | forced in | -0.0553 | no room as is (fit), worth less than what it displaces | Sunbeam |
| utility weapons | Tractor Beam | forced in | -0.0135 | no room as is (fit), worth less than what it displaces | Chameleon Anti-Missile |
| expansions | Outfits Expansion | one more | -0.00042 | fits, but worth less than what it displaces |  |

