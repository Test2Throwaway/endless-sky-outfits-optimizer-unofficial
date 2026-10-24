# Felsic

## boarder (optimized)

**Baseline (current numbers)** — score 0.633, route survivability: evasive

weapon capacity 68%, engine capacity 60%, batteries 1 (+750 energy capacity), secondaries 0, combat heat peak 68%, battery drawdown 38%, agility 36

```
 400 × Anti-Materiel Gun
   1 × Antimatter Power Cell
   1 × Bullfrog Anti-Missile
 400 × Cloud Piercer
   1 × Emergency Ramscoop
 131 × Enforcer Confrontation Gear
 400 × Enforcer Riot Staff
 400 × Fragmentation Grenades
   1 × Hyperdrive
   1 × Jump Drive
   2 × Ka'het Annihilator Turret
 400 × Kinetic Rail Rifle
 400 × Laser Rifle
 400 × Nerve Gas
 400 × Plasma Grenades
 400 × Plasmasickle
 400 × Pug Biodefenses
 400 × Pug Peacekeeping Staff
 400 × Pulse Rifle
   1 × Quantum Key Stone
 400 × Savagery Pike
   1 × Small Reactor Module
   1 × Small Repair Module
   1 × Small Steering Module
   1 × Small Thrust Module
   1 × Supercapacitor
 400 × Thermal Repeater Rifle
 400 × Tuning Rifle
   2 × Vapor Nuclear Rocket
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| boarding attack | +0.38 | +0.38 | 0.542 | beats 38 of 72 stock ships |
| weapon value | +0.25 | +0.25 | 0.854 | beats 57 of 67 stock ships |
| agility | +0.12 | +0.12 | 0.045 | beats 3 of 73 stock ships |
| boarding defense | +0.12 | +0.12 | 0.991 | beats 71 of 72 stock ships |
| max speed | +0.06 | +0.06 | 0.973 | beats 71 of 73 stock ships |
| anti-missile | +0.06 | +0.06 | 0.417 | beats 21 of 52 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Supercapacitor | one more | -1.38e-05 | fits, but worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff |
| generators | Small Reactor Module | one more | -8.89e-05 | breaks Cruising: heat, Recovery: shields and hull as is; worth less after making room | Enforcer Confrontation Gear, Enforcer Riot Staff, Antimatter Power Cell |
| coolers | Ka'het Primary Cooling | forced in | -0.000235 | breaks Combat (240 s): energy as is; worth less after making room | Enforcer Confrontation Gear, Enforcer Riot Staff |
| coolers | Cooling Module | forced in | -0.000156 | breaks Combat (240 s): energy as is; worth less after making room | Enforcer Confrontation Gear, Enforcer Riot Staff, Supercapacitor |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module, Supercapacitor |
| shield regen | "Jorv" Shield Cortex | forced in | — | can't pass: Combat (240 s): energy |  |
| hull repair | Small Repair Module | one more | -4.13e-05 | breaks Combat (240 s): energy as is; worth less after making room | Enforcer Confrontation Gear, Enforcer Riot Staff, Supercapacitor |
| engines | Vapor Nuclear Rocket | one more | 0.00231 | better: the search missed it | Enforcer Confrontation Gear, Enforcer Riot Staff |
| turrets | Ka'het Annihilator Turret | one more | — | can't pass: Fits (game rule), Combat (240 s): energy | Small Reactor Module |
| secondaries | Langrage Hyper-Heaver | forced in | -0.0604 | no room as is (fit), worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff, Antimatter Power Cell, Ka'het Annihilator Turret |
| secondaries | Firestorm Battery | forced in | — | can't pass: Magazine: Firestorm Torpedo | Supercapacitor, Antimatter Power Cell, Ka'het Annihilator Turret |
| anti-missile | Bullfrog Anti-Missile | one more | -0.034 | no room as is (fit), worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff, Antimatter Power Cell, Ka'het Annihilator Turret |
| utility weapons | Horizon Grappler | forced in | -0.0602 | no room as is (fit), worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff, Antimatter Power Cell, Ka'het Annihilator Turret |
| utility weapons | Tractor Beam | forced in | -0.0602 | no room as is (fit), worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff, Antimatter Power Cell, Ka'het Annihilator Turret |
| expansions | Cargo Expansion | forced in | -3.44e-05 | fits, but worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff |
| expansions | Outfits Expansion | forced in | -3.44e-05 | fits, but worth less than what it displaces | Enforcer Confrontation Gear, Enforcer Riot Staff |

## freighter (optimized)

**Baseline (current numbers)** — score 0.744, route survivability: evasive

weapon capacity 18%, engine capacity 98%, batteries 1 (+750 energy capacity), secondaries 0, combat heat peak —, battery drawdown —, agility 110

```
   1 × Anomalous Mass
   2 × Bullfrog Anti-Missile
   6 × Cargo Expansion
   1 × Cooling Module
   1 × Emergency Ramscoop
   3 × Heatsink Partition
   1 × Hyperdrive
   1 × Inductive Extractor
   1 × Jump Drive
   1 × Large Steering Module
   1 × Quantum Key Stone
   1 × Small Repair Module
   1 × Small Steering Module
   1 × Supercapacitor
   1 × Z-666 "Zap" Fusion Torch
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| cargo space | +0.60 | +0.60 | 0.611 | beats 41 of 72 stock ships |
| max speed | +0.18 | +0.18 | 0.987 | beats 72 of 73 stock ships |
| agility | +0.10 | +0.10 | 0.88 | beats 64 of 73 stock ships |
| acceleration | +0.07 | +0.07 | 1 | beats 72 of 73 stock ships |
| anti-missile | +0.05 | +0.05 | 0.835 | beats 43 of 52 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Supercapacitor | one more | -0.000459 | no room as is (fit), worth less than what it displaces | Anomalous Mass |
| generators | Triple Plasma Core | forced in | — | can't pass: Fits (game rule) | Inductive Extractor, Cargo Expansion, Anomalous Mass |
| generators | Lantern Fission Core | forced in | -0.0947 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Cargo Expansion, Large Steering Module |
| coolers | Cooling Module | one more | -0.000281 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Anomalous Mass |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module |
| shield regen | "Jorv" Shield Cortex | forced in | -0.0259 | no room as is (fit), worth less than what it displaces | Small Repair Module, Cargo Expansion |
| hull repair | Small Repair Module | one more | -0.00995 | no room as is (fit), worth less than what it displaces | Small Steering Module |
| turrets | Ultraviolet Excimer Laser | forced in | — | can't pass: Fits (game rule), Weapons in combat: energy | Small Steering Module, Cargo Expansion, Supercapacitor, Anomalous Mass |
| turrets | Blue Optical Laser | forced in | — | can't pass: Fits (game rule) | Cargo Expansion |
| secondaries | Langrage Hyper-Heaver | forced in | -0.095 | no room as is (fit), worth less than what it displaces | Cargo Expansion, Large Steering Module |
| secondaries | Firestorm Battery | forced in | — | can't pass: Magazine: Firestorm Torpedo | Cargo Expansion, Supercapacitor, Large Steering Module |
| anti-missile | Bullfrog Anti-Missile | one more | -0.0168 | no room as is (fit), worth less than what it displaces | Cargo Expansion |
| utility weapons | Horizon Grappler | forced in | -0.0754 | no room as is (fit), worth less than what it displaces | Large Steering Module |
| utility weapons | Tractor Beam | forced in | -0.0753 | no room as is (fit), worth less than what it displaces | Large Steering Module |
| expansions | Cargo Expansion | one more | -0.0573 | no room as is (fit), worth less than what it displaces | Large Steering Module |

## scavenger (optimized)

**Baseline (current numbers)** — score 0.689, route survivability: evasive

weapon capacity 95%, engine capacity 96%, batteries 1 (+750 energy capacity), secondaries 1, combat heat peak —, battery drawdown —, agility 100

```
   4 × Anomalous Mass
   1 × Bow Drive (Meteor Class)
   1 × Cargo Expansion
   1 × Chiisana Rift Steering
   1 × Emergency Ramscoop
   1 × Heatsink Partition
   1 × Hyperdrive
   1 × Jump Drive
   1 × Langrage Hyper-Heaver
   1 × Lantern Fission Core
   1 × Quantum Key Stone
   1 × R-180 RCS Thrusters
   1 × Small Repair Module
   1 × Small Reverse Module
   1 × Supercapacitor
   2 × Thruster (Asteroid Class)
   1 × Tractor Beam
   1 × Vapor Nuclear Rocket
   1 × Wanderer Anti-Missile
```

Looks right? ☐ yes ☐ no — Plays right? ☐ yes ☐ no — notes:

Score breakdown:

| metric | weight | balance weight | score | standing |
|---|---|---|---|---|
| cargo space | +0.45 | +0.45 | 0.488 | beats 35 of 72 stock ships |
| maneuverability | +0.18 | +0.18 | 0.791 | beats 62 of 73 stock ships; beats 52 of 73 stock ships |
| agility | +0.14 | +0.14 | 0.788 | beats 57 of 73 stock ships |
| push force | +0.10 | +0.10 | 0.945 | beats 48 of 51 stock ships |
| max speed | +0.07 | +0.07 | 0.964 | beats 70 of 73 stock ships |
| anti-missile | +0.07 | +0.07 | 0.893 | beats 46 of 52 stock ships |

Why each class is or isn't used:

| class | outfit | tried | score change | reason | displaced |
|---|---|---|---|---|---|
| batteries | Supercapacitor | one more | -0.00145 | no room as is (fit), worth less than what it displaces | Anomalous Mass |
| generators | Lantern Fission Core | one more | -0.0925 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Langrage Hyper-Heaver |
| coolers | Ka'het Primary Cooling | forced in | -0.0925 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Langrage Hyper-Heaver |
| coolers | Cooling Module | forced in | -0.0481 | no room as is (fit), worth less than what it displaces | Heatsink Partition, Cargo Expansion |
| shield regen | Shield Relay Booster | forced in | — | can't pass: Fits (game rule) | Small Repair Module |
| shield regen | "Jorv" Shield Cortex | forced in | — | can't pass: Weapons in combat: energy | Small Repair Module, Cargo Expansion, Langrage Hyper-Heaver |
| hull repair | Small Repair Module | one more | -0.0449 | no room as is (fit), worth less than what it displaces | Cargo Expansion |
| engines | Thruster (Asteroid Class) | one more | — | can't pass: Weapons in combat: energy | Vapor Nuclear Rocket |
| turrets | Ultraviolet Excimer Laser | forced in | — | can't pass: Fits (game rule), Weapons in combat: energy | Small Reverse Module, Supercapacitor, Langrage Hyper-Heaver, R-180 RCS Thrusters, Chiisana Rift Steering |
| turrets | Blue Optical Laser | forced in | — | can't pass: Fits (game rule), Weapons in combat: energy | Supercapacitor, Langrage Hyper-Heaver |
| secondaries | Langrage Hyper-Heaver | one more | — | can't pass: Fits (game rule), Anti-missile | Cargo Expansion, Wanderer Anti-Missile, Anomalous Mass |
| anti-missile | Wanderer Anti-Missile | one more | -0.0917 | no room as is (fit), worth less than what it displaces | Langrage Hyper-Heaver |
| utility weapons | Tractor Beam | one more | -0.0958 | no room as is (fit), worth less than what it displaces | Langrage Hyper-Heaver |
| expansions | Cargo Expansion | one more | -0.0648 | no room as is (fit), worth less than what it displaces | Langrage Hyper-Heaver |

