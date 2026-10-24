# Scoring experiments (branch experiment/scoring-options)

Main branch scoring is unchanged; everything here is behind switches whose defaults reproduce it.

## Why

A Kar Ik Vot 349 warship kept spending outfit space on regeneration (2× the stock shield regen, 6× the hull repair)
instead of weapons (0.6× the stock raw damage). The cause is the scoring, not the weapon discounts:

- Every metric is scored by its place on a ladder of all stock ships. An optimized heavy warship beats nearly every
  stock ship of any size on every metric, so all its scores sit at the very top, where the remaining rungs are a few
  huge ships (boss ships such as the Archon C: 300,608 weapon value, 6,000 shield regen). Extra weapons or regen
  gain crumbs, and which crumb is biggest per outfit space depends on how those top ships happen to be spaced.
- The total is a weighted sum: there is no penalty for a lopsided design (90% on one metric, 20% on another).

## Switches (`optimize`, `tools/repeat_optimize.py`, `tools/experiment.py`)

`--reference` — which stock ships a design is scored against:

| mode | ladder |
|---|---|
| legacy | every stock ship (main branch) |
| all | every stock ship except Superheavy, Unclassified, Unclassified Minor, Game Mechanics and uncategorized |
| family | the hull's class family: light/medium/heavy warships; light/heavy freighters; transports and space liners; interceptors, fighters and drones; utility |
| class | the hull's own category (widens to family, then all, where fewer than 5 ships have the metric) |
| stock | improvement over this hull's stock design: log2(1 + value ÷ stock value) ÷ 2, so stock = 0.5, 3× = 1, 7× = 1.5 (every doubling of a large improvement adds about the same). Metrics the stock design lacks use the family ladder. |

`--combine` — how metric scores combine within a route:

| mode | rule |
|---|---|
| sum | weighted sum (main branch) |
| power:0.5 | weighted power mean (p = 0.5) × total weight: lopsided designs lose some score |
| power:0 | weighted geometric mean: lopsided designs lose a lot (one weak metric drags everything) |

`--weapon-tweaks` — homing weapons skip the fire-rate, fixed-gun and projectile-speed discounts (they steer and
fire bursts by design); the fixed-gun and short-range discounts become straight lines instead of squared.

## Class notes (user)

1. Transport: lightweight jack of all trades, emphasis on passenger transport.
2. Space liner: bulk passenger transport (bunks not needed by crew); sometimes repurposed as raiders alongside
   combat ships that disable.
3. Light freighter: goods transport (cargo) that can't carry much, but maneuverable and survivable enough to operate
   mostly unescorted.
4. Heavy freighter: massive bulk goods transport, terrible maneuverability, survival relies on escorts or peaceful
   space.
5. Utility: grab bag of ships that fit no other role.
6. Interceptor: small, weak warship just big enough for a hyperdrive; beyond early play only makes sense in swarms,
   expect casualties.
7. Light to heavy warship: fighting ships from small, lightly armed, nimble ships to massive lumbering ships
   bristling with weapons.
8. Superheavy: defined by massive size; generally excluded from calculations.
9. Fighter: an interceptor, but smaller and without a hyperdrive.
10. Drone: a fighter, but smaller.
11.–13. Unclassified, Unclassified Minor, Game Mechanics: excluded from calculations.

## Test plan

Warship role on Kar Ik Vot 349 (heavy), Firebird (medium) and Argosy (light freighter as warship); every
reference × combine mode, weapon tweaks off and on; two runs each (180 runs). Each design is measured against
that hull's stock design on raw numbers that don't depend on the scoring rules: raw damage, shield regen, hull
repair, anti-missile, turn, acceleration, speed, outfit space split, weapon capacity used, guns, turrets and
secondary weapons.
