# Fleet control in combat (Endless Sky 0.11.2, from the source)

The player flies one ship directly. Every other ship in the fleet is flown by the game's AI, steered by the
player's orders and a few preferences. Sources: `source/AI.cpp` (UpdateKeys, IssueOrder, FollowOrders, FindTarget,
AutoFire), `source/Command.cpp`, `source/Preferences.cpp`, `source/Engine.cpp` (mouse orders).

## The orders

Orders go to the **selected escorts**, or to the whole fleet if none are selected (escorts are selected by
clicking their icons). Parked ships never get orders.

| Order (default key, from `keys.txt`) | What the escorts do |
|---|---|
| **Fight my target** (F) | Everyone attacks the flagship's target; "finish off" if it's disabled. This is focus fire. Also works on an asteroid (mine it). |
| **Hold fire** (Y) | Toggle: stop firing. The only order that includes the flagship (it blocks autofire). |
| **Hold position** (H) | Stop where they are; keep turning to aim at their target, but don't chase. |
| **Gather around me** (G) | Return to the flagship: circle it, or fly in **formation** if one is set. Shift + gather cycles formation patterns. |
| **Move to** (right-click in space, or a map destination) | Fly to that point (or system) and hold there. On arrival it becomes "hold position". |
| **Harvest flotsam** (Z) | Collect flotsam. |
| **Scan my target** | Scan it (needs a cargo or outfit scanner in the fleet). |
| **Toggle ammo usage** (U) | Cycles the preference: escorts use ammo **always** (default), **frugally**, or **never**. |
| **Deploy / recall fighters** | Carried craft launch or dock. |
| **Fleet jump** | The fleet jumps together. |

There's no order for "retreat", "stay at range X", "protect that ship" or "use these weapons".

## What escorts do on their own (no order)

- **Targets.**
  - Each escort picks the **closest enemy**: within 4,000, or within 1.5 × its longest range if all its weapons
    reach over 1,000.
  - It prefers its previous target, or the flagship's target (counted 500 closer).
  - It spreads out: a foe already targeted by more than two ships counts as farther away.
  - It won't chase a foe more than twice its own strength beyond 1,000, unless it's "daring".
- **Movement.** It attacks its target with the standard AI attack moves. With no target, it follows the flagship:
  in formation, or circling.
- **Firing.**
  - Autofire takes every weapon in range.
  - Turrets focus on the ship's target by default ("Turrets focus fire" on); with it off they're opportunistic.
- **Ammo:** used freely by default.
  - Frugal mode holds ammo weapons back while the escort is above 75% health and its side isn't outgunned.
  - Homing ammo weapons never fire without a target.
- **Never retreats.** Player ships never flee, however damaged or empty of ammo (NPCs do). Damaged fighters return
  to their carrier ("Damaged fighters retreat", on by default).
- **Follows the flagship's jumps,** unless ordered to hold position or move somewhere.

## What this means for ship design

1. **The flagship's job shifts with fleet size** (your point). Alone, it's the fighter. In a large fleet it's the
   commander: picks the target (focus fire hangs on its target), positions the fleet (move to, hold position),
   and needs to survive and see. Weapons matter less than durability, sustain, speed to reposition, and range to
   pick targets. A "fleet commander" role, weighted away from firepower, would cover that.
2. **Escorts are AI-flown** (the optimizer's `pilot = "ai"` lever):
   - **No retreat**, so durability and sustain matter more than for a player ship that can back off.
   - **Autofire with every weapon in range**, so a weapon's duty is set by range and target choice, not the
     player's judgement.
   - **Closest-target selection**, so short-range escorts reach targets first. Long-range-only escorts engage
     from up to 1.5× their range.
   - **Ammo spent freely** unless the player switches to frugal: magazines empty faster than a player would empty
     them. The fights-per-restock question matters more for escorts.
3. **Positioning orders make some roles workable:** hold position for a fight anchor or sniper line, move to for
   a picket. Focus fire makes a few high-damage escorts more useful than many spread-out ones.
4. **There's no per-ship engagement range or retreat threshold.** The player can't tell one escort to hang back.
   Designs that only work at long range, or only work if they retreat early, behave badly as escorts. They suit
   the flagship better.

## Open questions for you

- Should the optimizer get a **fleet commander** role (flagship in a large fleet: survivability, sustain,
  repositioning speed, sensors), separate from the player-flown fighter?
- Should **escort roles assume AI piloting** by default (no retreat, autofire, free ammo), and player-flown
  roles assume the player's control (retreat possible, chosen engagement)?
- Fleet size: do you want a "fleet size" setting that moves the flagship from fighter to commander gradually?
