# Role files

A role says what a ship is for. A design request combines one to three roles. Roles are TOML files; the tool
ships with a few (`es_optimizer/roles/`) and you can add your own in your settings folder under `roles/`
(`es-optimizer role-copy scavenger my-scavenger` makes an editable copy). A role of yours with the same file name
as a bundled one replaces it.

The sections follow how a design request is usually thought about:

- **should**: the baseline, what to optimize and with what relative weights.
- **must**: hard requirements, and `emphasize`: things to weigh much more heavily than the baseline suggests.
- **may**: things the baseline would give little or no weight, now given some real weight, but never top priority.
- **must_not**: the ship must not have it; also switches off a default requirement for it (jump drive, anti-missile, …).
- **should_not**: actively avoided, but accepted if worth enough (a negative weight).

```toml
name = "In-combat scavenger"
description = "Present at battles, survives them, picks up what falls out of destroyed ships."

[ship]                 # how the design rules apply (all optional)
combat = false         # combat ship (all weapons continuously) or not (50% continuously, all for 2.5 s)
fighter = false        # fighters and drones use the non-combat weapon rules
hero = false           # the ship you fly yourself: no afterburner
goal = "normal"        # normal | disable | capture-intact | destroy
fight = "dedicated"    # dedicated (4 min fights) | escort (90 s)
evader = false         # must survive long periods far from a dim star
must_run_dark = false  # no solar power
long_range = false     # never needs to refuel at planets
needs_ramscoop = true
needs_drives = true    # hyperdrive, jump drive, quantum keystone
needs_anti_missile = true
capture_targets = []   # capture-intact targets (default: unbuyable Pug, Korath, Heliarch, Ka'het, Quarg warships)

[should]               # baseline: relative weights
survivability = 3      # a composite (see below) or a metric
maneuverability = 2
deprioritize = []      # metrics/composites cut to 10% of their weight, even if another role weights them

[must]
has = ["tractor beam"]               # hard: metric must be above 0
min = {}                             # hard: e.g. { "cargo space" = 100 }
max = {}                             # hard
reverse_thrust = "balanced"          # hard: useful | balanced | nimble
emphasize = ["cargo space"]          # 50% of the score between them; or a share each: { "cargo space" = 0.6 }

[may]
bonus = ["push force"]               # 10% of the score between them; or { "push force" = 0.05 }

[must_not]
have = []              # metric must be 0, e.g. ["jump drive", "anti-missile"]; overrides default requirements

[should_not]
have = []              # −20% of the score between them; or { "reverse thrust" = 0.1 }

[outfits]              # optional outfit filter by tag, for roles that truly exclude something
forbid = []
allow = []             # allow wins over forbid for an outfit with both tags

[metrics.my-composite] # optional: define composites for this role
"effective shields" = 1
"shield regen" = 2
```

Metrics not mentioned anywhere get no weight: a non-combat role that doesn't mention firepower can still carry
weapons, but they are not valued.

## Metrics

Named metrics: `max speed`, `acceleration`, `reverse acceleration`, `turn rate`, `agility`, `effective shields`,
`effective hull`, `shield regen`, `hull repair`, `weapon value` (damage per second weighted by the goal, after the
range and fixed-gun penalties), `shield dps`, `hull dps`, `anti-missile`, `tractor beam`, `push force`,
`pull force`, `jumps`, `free outfit space`. Any outfit or hull attribute (`cargo space`, `ramscoop`, `bunks`,
`scan interference`, …) also works, totalled over the ship.

Composites are named weighted mixes of metrics, defined in `_metrics.toml` (bundled: `survivability`,
`maneuverability`, `speed`, `firepower`) or in a role's own `[metrics.NAME]` table.

## Tags

`damage weapon`, `anti-missile`, `tractor beam`, `push weapon` (hit force at least 2× its damage), `pull weapon`
(pull force at least 1× its damage), `instantaneous`, `shield disruption`, `missile` (can be shot down),
`fuel weapon`, `afterburner`, `cloak`, `illegal`, `solar`, `ramscoop`, `torch`.

## Combining roles

- `[ship]`: a setting that is on in any role is on (combat, hero, evader, …); "needs" settings stay on unless
  every role turns them off; the longest fight wins; roles must agree on the goal.
- `[must]`: all hard requirements apply; for the same metric the strictest wins; a min above a max is an error.
- `[must_not]`: everything listed in any role is excluded; listing something another role must have is an error.
- Weights are built in steps within each role: `should` sets the baseline (100%); `must` emphasize takes 50%,
  scaling everything before it to 50%; `may` takes 10% (earlier weights × 0.9); `should_not` takes −20%
  (earlier weights × 0.8). A step's strength never depends on how many items earlier sections have. Each role
  then counts equally, and deprioritized metrics are cut to 10%.
- `[outfits]`: forbidden tags from every role apply; allowed tags from every role override them.

## How weights are scored

Metrics have different units, so the optimizer scores each one against the best this hull can reach for that
metric alone (0 = worst, 1 = best), then adds them with the weights. `evaluate` shows the raw values.
