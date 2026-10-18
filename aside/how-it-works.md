# How the optimizer works

## For an Endless Sky player

This is a loadout designer for Endless Sky. You give it a hull, say an Argosy or a Kar Ik Vot 349, and what you
want the ship to do (warship, freighter, interceptor, and so on). It works out the best combination of outfits to
install. It only uses outfits you could really get: ones you can buy with your licences, or plunder from ships of
governments you're willing to fight. It discards any loadout that wouldn't work in practice. To survive, a loadout
has to:

- fit the outfit, weapon and engine space;
- cruise and recharge shields and hull indefinitely without overheating or running dry;
- for combat ships, fire everything through a full fight (90 seconds for escorts, 4 minutes for dedicated
  warships) without overheating or running out of energy;
- carry a hyperdrive or jump drive and enough fuel;
- have at least some shield or hull regeneration;
- not be so sluggish it can't turn.

Each loadout that survives is graded against every stock ship in the game, metric by metric: weapon damage
(adjusted for range, fire rate, turret speed and projectile speed), shield regen, hull repair, turning,
acceleration, anti-missile and so on. Scoring like a typical stock ship on a metric gives 0.5, and matching the
best stock ship gives 1. The role decides how much each metric matters, and lets a warship be judged as either a
slow tank or an evasive dogfighter, whichever suits the hull better. With hundreds of outfits, trying every
combination is impossible, so the search runs in two stages:

1. A mathematical optimizer suggests strong loadouts quickly from a dozen different starting points. One might
   start "mostly weapons, light engines" and another "tank build", all running in parallel on your CPU.
2. Each promising loadout gets hand-tuned. The tool removes outfits that do nothing, then tries adding, removing
   and swapping outfits one at a time or in small groups. It keeps any change that improves the grade, and settles
   ties by wasting the least space.

You get the best loadout found, with its grade, how each metric compares with stock ships, and the full list of
checks it passed.

## Technical summary

A design is only allowed if it passes every check: capacities, sustain (cruising, recovery and the designed combat
lengths, for heat and energy), fuel, drives, some regeneration, and the role's minimum turn rate and acceleration.
Among the designs that pass, each metric is scored on a percentile ladder of the stock ships (0.5 typical, 1 the
best, a gentle slope beyond), and the scores are combined with the role's weights. Where a role offers
alternatives (durable tank versus evasive), the better route counts.

The search has two stages:

1. **Integer solver.** OR-Tools CP-SAT picks whole numbers of each outfit. Heat, agility and mass don't fit its
   linear model directly, so they are approximated as straight lines around the current design; the solver solves,
   re-approximates around the new answer and repeats until the design settles, checking each one with the exact
   calculator. This runs from a dozen or so starting points (survivability routes × weapon and engine budgets),
   spread over the CPU cores.
2. **Polish.** The best few designs go through the exact calculator only: strip outfits that do nothing; try
   adding, removing and swapping single outfits, groups and pairs; keep any change that raises the score; break
   ties by the least wasted space.

The highest-scoring design wins and is printed with its score breakdown, its checks and how each starting point
did.
