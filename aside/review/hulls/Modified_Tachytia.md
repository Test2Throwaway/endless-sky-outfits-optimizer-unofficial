# Modified Tachytia

## boarder (optimized)

**Baseline (current numbers)** — score 1.768, route survivability: durable

weapon capacity 63%, engine capacity 13%, batteries 0 (+24500 energy capacity), secondaries 0, combat heat peak 90%, battery drawdown 37%, agility 11

```
 400 × Anti-Materiel Gun
   6 × Antimatter Power Cell
   7 × Blue Optical Laser
   2 × Blue Sun Reactor
 400 × Enforcer Confrontation Gear
   1 × Green Optical Laser
   3 × Heatsink Partition
   1 × Jump Drive
   1 × Large Cogeneration Module
   2 × Large Reactor Module
   1 × Maeri Engine Nacelles
   1 × Microbot Defense Station
   5 × Optical Lasing Generator
  28 × Outfits Expansion
  21 × Overcharged Shield Module
   3 × Photoelectric Lamina
   1 × Plasmadyne Scoop
 400 × Pug Biodefenses
   1 × Quantum Keystone
   1 × Scram Drive
   1 × Small Cogeneration Module
   1 × Wanderer Anti-Missile
   1 × White Sun Reactor
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| boarding attack | +0.36 | +0.36 | 1.27 | beats 72 of 72 stock ships |
| weapon value | +0.24 | +0.24 | 1.07 | beats 67 of 67 stock ships |
| shield regen | +0.12 | +0.12 | 4.7 | beats 61 of 61 stock ships |
| boarding defense | +0.12 | +0.12 | 3.71 | beats 72 of 72 stock ships |
| hull repair | +0.06 | +0.06 | 0.167 | beats 4 of 30 stock ships |
| anti-missile | +0.06 | +0.06 | 0.895 | beats 46 of 52 stock ships |
| pull force | +0.05 | +0.05 | 0 | beats 0 of 11 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Crystal Capacitor | forced in | 0 | no room as is (fit), worth less than what it displaces | Small Cogeneration Module |
| batteries | Large Battery Module | forced in | 0 | no room as is (fit), worth less than what it displaces | Small Cogeneration Module |
| generators | Antimatter Power Cell | one more | -0.0238 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Small Cogeneration Module, Large Cogeneration Module, Overcharged Shield Module, Outfits Expansion |
| coolers | Ka'het Primary Cooling | forced in | -0.0167 | no room as is (fit), worth less than what it displaces | Blue Optical Laser, Small Cogeneration Module, Outfits Expansion |
| coolers | Cooling Module | forced in | -0.000127 | breaks Combat (240 s): energy as is; worth less after making room | Green Optical Laser, Small Cogeneration Module, Outfits Expansion |
| shield regen | Overcharged Shield Module | one more | -0.0455 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Blue Optical Laser, Small Cogeneration Module, Outfits Expansion, Antimatter Power Cell, Wanderer Anti-Missile |
| hull repair | Nanite Enhancer | forced in | — | can't pass: Fits (game rule) |  |
| hull repair | Overclocked Repair Module | forced in | 0.0184 | better: the search missed it | Heatsink Partition, Large Cogeneration Module, Overcharged Shield Module, Outfits Expansion |
| engines | Maeri Engine Nacelles | one more | -0.0177 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Optical Lasing Generator, Blue Optical Laser, Small Cogeneration Module, Large Cogeneration Module, Outfits Expansion |
| guns | Drag Cannon | forced in | — | can't pass: Fits (game rule) | Green Optical Laser, Antimatter Power Cell |
| guns | Heavy Ion Cyclotron | forced in | — | can't pass: Fits (game rule) | Blue Optical Laser, Small Cogeneration Module, Antimatter Power Cell |
| turrets | Blue Optical Laser | one more | — | can't pass: Fits (game rule), Combat (240 s): energy | Green Optical Laser, Large Reactor Module |
| secondaries | Ka'het Emergency Deployer | forced in | — | can't pass: Fits (game rule), Combat (240 s): heat, Magazine: Ka'het MHD Generator | Small Cogeneration Module |
| secondaries | External Launch Tube | forced in | — | can't pass: Fits (game rule), Magazine: "Orchid" Nuclear Missile | Large Cogeneration Module, Overcharged Shield Module |
| anti-missile | Green Optical Laser | one more | -0.0166 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Blue Optical Laser, Small Cogeneration Module, Outfits Expansion, Antimatter Power Cell |
| expansions | Outfits Expansion | one more | — | can't pass: Combat (240 s): energy | Large Reactor Module |

## freighter (optimized)

**Baseline (current numbers)** — score 1.791, route survivability: evasive

weapon capacity 93%, engine capacity 100%, batteries 0 (+2000 energy capacity), secondaries 0, combat heat peak —, battery drawdown —, agility 26

```
   1 × "Basrem" Atomic Steering
  31 × Cargo Expansion
   1 × Concentrating Solar Array
   1 × Emergency Ramscoop
  30 × Heatsink Partition
   1 × Hyperdrive
   1 × Jump Drive
   4 × Large Reactor Module
   1 × OC-"Mavra" Betavoltaic Cell
   3 × Photoelectric Lamina
   1 × Quantum Key Stone
   1 × Small Thrust Module
   7 × Wanderer Anti-Missile
   1 × Z-333 "Spark" Fusion Torch
   6 × Z-666 "Zap" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| cargo space | +0.60 | +0.60 | 1.19 | beats 72 of 72 stock ships |
| max speed | +0.18 | +0.18 | 4.88 | beats 73 of 73 stock ships |
| agility | +0.10 | +0.10 | 0.0133 | beats 0 of 73 stock ships |
| acceleration | +0.07 | +0.07 | 1.06 | beats 73 of 73 stock ships |
| anti-missile | +0.05 | +0.05 | 2.17 | beats 52 of 52 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Crystal Capacitor | forced in | -0.00377 | no room as is (fit), worth less than what it displaces | Cargo Expansion |
| batteries | Large Battery Module | forced in | -0.00379 | no room as is (fit), worth less than what it displaces | Cargo Expansion |
| generators | Large Reactor Module | one more | -0.317 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Photoelectric Lamina, Z-333 "Spark" Fusion Torch, Z-666 "Zap" Fusion Torch, Concentrating Solar Array |
| coolers | Ka'het Primary Cooling | forced in | -0.11 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Z-333 "Spark" Fusion Torch, Concentrating Solar Array |
| coolers | Cooling Module | forced in | -0.0118 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Wanderer Anti-Missile |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Cargo Expansion |
| shield regen | "Jorv" Shield Cortex | forced in | -0.224 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Photoelectric Lamina, Z-666 "Zap" Fusion Torch, Concentrating Solar Array |
| hull repair | Nanite Enhancer | forced in | — | can't pass: Fits (game rule) | Cargo Expansion |
| hull repair | Overclocked Repair Module | forced in | -0.11 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Photoelectric Lamina, Z-333 "Spark" Fusion Torch, Concentrating Solar Array |
| guns | Drag Cannon | forced in | -0.00377 | no room as is (fit), worth less than what it displaces | Cargo Expansion |
| guns | Speckle Coilgun | forced in | — | can't pass: Magazine: Speck Round | Wanderer Anti-Missile |
| turrets | Ultraviolet Excimer Laser | forced in | -0.236 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Photoelectric Lamina, Z-666 "Zap" Fusion Torch, Wanderer Anti-Missile, Concentrating Solar Array |
| turrets | Blue Optical Laser | forced in | — | can't pass: Fits (game rule) | Heatsink Partition, Photoelectric Lamina, Z-333 "Spark" Fusion Torch, Concentrating Solar Array |
| secondaries | Ka'het Emergency Deployer | forced in | — | can't pass: Magazine: Ka'het MHD Generator | Heatsink Partition, Photoelectric Lamina, Large Reactor Module, OC-"Mavra" Betavoltaic Cell |
| secondaries | External Launch Tube | forced in | — | can't pass: Magazine: "Orchid" Nuclear Missile | Wanderer Anti-Missile, Concentrating Solar Array |
| utility weapons | Horizon Grappler | forced in | -0.0156 | no room as is (fit), worth less than what it displaces | Cargo Expansion, Wanderer Anti-Missile |
| utility weapons | Tractor Beam | forced in | -0.0119 | no room as is (fit), worth less than what it displaces | Wanderer Anti-Missile |
| expansions | Cargo Expansion | one more | -0.00808 | no room as is (fit), worth less than what it displaces | Wanderer Anti-Missile, Concentrating Solar Array |

## scavenger (optimized)

**Baseline (current numbers)** — score 1.661, route survivability: durable

weapon capacity 51%, engine capacity 4%, batteries 1 (+2400 energy capacity), secondaries 1, combat heat peak —, battery drawdown —, agility 1

```
   1 × Afterburner (Asteroid Class)
   5 × Heatsink Partition
   1 × Hyperdrive
   1 × Jump Drive
   1 × Ka'het Reserve Accumulator
   1 × Langrage Hyper-Heaver
   1 × Lantern Fission Core
   5 × Large Reactor Module
   1 × Magnetoplasma Drive
   2 × Nanite Enhancer
  20 × Outfits Expansion
  29 × Overcharged Shield Module
   3 × Photoelectric Lamina
   1 × Quantum Key Stone
   1 × S-270 Regenerator
   1 × Small Nanite Fabricator
   2 × Small Reactor Module
   1 × Tractor Beam
   1 × Wanderer Anti-Missile
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| cargo space | +0.49 | +0.49 | 0.988 | beats 71 of 72 stock ships |
| shield regen | +0.15 | +0.15 | 6.33 | beats 61 of 61 stock ships |
| push force | +0.11 | +0.11 | 0.945 | beats 48 of 51 stock ships |
| hull repair | +0.07 | +0.07 | 0.87 | beats 26 of 30 stock ships |
| anti-missile | +0.07 | +0.07 | 0.893 | beats 46 of 52 stock ships |
| pull force | +0.05 | +0.05 | 0 | beats 0 of 11 stock ships |
| maneuverability | +0.05 | +0.05 | 0.000645 | beats 0 of 73 stock ships; beats 0 of 73 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Ka'het Reserve Accumulator | one more | -7.68e-09 | fits, but worth less than what it displaces |  |
| generators | Large Reactor Module | one more | -0.102 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Lantern Fission Core, Outfits Expansion, Langrage Hyper-Heaver, Small Reactor Module |
| coolers | Ka'het Primary Cooling | forced in | -0.0291 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Overcharged Shield Module, Outfits Expansion |
| coolers | Cooling Module | forced in | -1.92e-08 | fits, but worth less than what it displaces |  |
| shield regen | Overcharged Shield Module | one more | — | can't pass: Weapons in combat: energy | Heatsink Partition, Large Reactor Module |
| hull repair | Nanite Enhancer | one more | — | can't pass: Fits (game rule) |  |
| engines | Magnetoplasma Drive | one more | -0.00384 | no room as is (fit), worth less than what it displaces | S-270 Regenerator |
| guns | Drag Cannon | forced in | -0.00387 | no room as is (fit), worth less than what it displaces | S-270 Regenerator |
| guns | Speckle Coilgun | forced in | — | can't pass: Magazine: Speck Round |  |
| turrets | Ultraviolet Excimer Laser | forced in | — | can't pass: Fits (game rule), Weapons in combat: energy | Heatsink Partition, Large Reactor Module, Outfits Expansion, Small Reactor Module |
| turrets | Blue Optical Laser | forced in | — | can't pass: Fits (game rule) | Overcharged Shield Module |
| secondaries | Langrage Hyper-Heaver | one more | -0.0262 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Lantern Fission Core, Overcharged Shield Module, Outfits Expansion |
| anti-missile | Wanderer Anti-Missile | one more | -0.0246 | no room as is (fit), worth less than what it displaces | Photoelectric Lamina, Overcharged Shield Module, Outfits Expansion |
| utility weapons | Tractor Beam | one more | -0.0291 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Photoelectric Lamina, Overcharged Shield Module, Outfits Expansion |
| expansions | Outfits Expansion | one more | — | can't pass: Fits (game rule) | Heatsink Partition |

