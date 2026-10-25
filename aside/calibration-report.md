# Calibration report, round 1

**What this is.** You said the designs never look right: no batteries, never running hot, no missiles, low weapon
use. This round collects the evidence to pair with your "looks right / plays right" judgement. It shows which numbers
move which symptom. It doesn't decide the right values; that needs your marks on the review sheets.

**Data.**
- **283 optimizer runs:** 151 hull × role runs plus 132 full re-solves under alternative settings. 269 ran on your
  PC with your current settings; 14 ran in the cloud container with my copy of them.
- **734 stock ships** judged by the same rules.
- Tables: `aside/calibration-data.md`. Review sheets: `aside/review/index.md`. Raw results:
  `experiments/calibration/jobs/`.

## The short version

| Symptom | Main cause found | Strongest lever | Candidate values to try |
|---|---|---|---|
| No batteries | Nothing values stored energy. At 100% weapon duty generation must cover everything, so batteries are pure dead weight (forcing one in: score change ±0.000 in every try). | A burst metric (`alpha dps`, built), plus a lower primary duty | alpha dps 10–20% of the score; primary duty 60–80% |
| Weapon use low | Weapon value sits above the best stock ship (the tail, half slope), so more guns score little; firepower is 50% of a warship's score at most. | Firepower share (`--emphasize firepower=0.5`): +15% weapon capacity on average, Argosy and Melodikos up to 98% | firepower 40–60% |
| No missiles / secondaries | The magazine rule: 2 fights' worth of ammo. Stock warships carry a median of **0.83** fights. 132 of 149 forced secondaries failed it. | fights per restock 2 → 1; weapon tweaks | fights per restock 1; tweaks on |
| Never runs hot | Designs already peak at 77–81% heat at the end of a fight (stock median 72–75%). Heat isn't the binding limit. | Not heat: see below | keep the 90% cap |
| Stock warships fail our rules | Combat energy: only 34–42% pass. Stock ships assume weapons don't fire all the time. | Primary duty: 70% → 59–67% pass; 50% → 76–86% pass. Fight length barely matters. | primary duty 60–70% |

## Findings in detail

### 1. Batteries

- **Designs:** heavy warships 12% carry a battery outfit, medium warships 30%, light warships 53%. Stock: about 90%
  in every class.
- **Battery drawdown in combat: 0% for every warship design.** The batteries designs do carry are never drained.
- **Class report:** forcing the best battery in changes the score by ±0.000 (139 tries). Batteries are worth exactly
  their space and nothing more: no metric scores stored energy, and the rules don't need it.
- **Why.** The combat rule requires energy for the whole fight at 100% primary duty. A deficit of D per second over
  240 s needs a battery of 240·D, which is never cheaper than generation. So batteries only appear when they come
  free with something else.
- **Lever.** Something must value a full opening burst. `alpha dps` (damage per second over the first 10 s, limited
  by batteries plus generation) does that. The one test with alpha at 15% (Enforcer, candidate D): a battery appears
  and drains to 46% over the fight.
- **Your call:** is "full-rate opening, then tapering off" how fights play? If yes, alpha dps 10–20% is the lever.
  Your "energy runs out before heat does" idea is the same thing from the rule side.

### 2. Weapon use

- **Designs:** warships use 66–71% of weapon capacity, freighters and liners 11–49%. Stock: warships 82–91%,
  freighters 76–87%.
- **Phase 2 (full re-solves):**

| Setting | Effect on weapon capacity used |
|---|---|
| firepower 50% | +15% (Argosy 53→98%, Melodikos 57→98%, Harmonikos 48→69%) |
| primaries 60% + weapon tweaks + firepower 50% | +17%, and secondaries appear on 3 of 6 hulls |
| primaries 60% alone | −5%: freed energy goes into survivability, not more guns |
| balance 0.5 | −2% on average, but uneven: KIV 82→55%, Enforcer 80→95%, Melodikos 57→81% |
| min shots 2 (fire-rate penalty below 2 shots/s instead of 6) | −14% |

- **Why.** On most hulls, weapon value already beats almost every stock ship in its class (the Kar Ik Vot beats 123
  of 124). Above the best stock ship each further 100% adds only half the score (`TAIL_SLOPE` 0.5), so more weapons
  earn little.
- **Levers:** the firepower share (role weight), and possibly `TAIL_SLOPE` (not swept this round).

### 3. Secondaries (missiles)

- **Designs:** heavy warships 56%, medium 40%, light 0%. Most of those are roles that demand them (missile boat
  60%) or pull secondaries (fight anchor). Plain warship and escort designs essentially never take a missile.
- **The magazine rule** asks for 2 fights' worth of ammo (`fights_per_restock = 2`), with long-range magazine weapons
  used in the opening 35% (dedicated) or 50% (escort) of a fight. For two 240 s fights: 168 Sidewinders, 1,920 Javelins
  for a Javelin Pod, 840 slugs for a Railgun.
- **Stock warships** carry a median of 0.83 of one fight's worth (quartiles 0.54–1.04). The rule is about 2.4× what
  the game's own ships carry.
- **Class report:** 132 of 149 forced secondaries still failed the magazine rule after making room. (The repair step
  adds ammo one at a time, so this overstates it a little; the rule is still the wall.)
- **Weapon tweaks** (homing weapons skip the fire-rate, fixed-gun and projectile-speed discounts) brought secondaries
  in on 2 of 6 hulls by themselves.
- **Your call:** how many fights does a player ship fight between restocks? NPC ships never restock; players do.
  1 fight matches stock habits.

### 4. Heat

- **Designs** peak at 77–81% of max heat at the end of a combat (median by class), close to the 90% cap. Stock
  warships: median 72–75%, top 10% above 100%.
- **HEAT_TARGET 100%** barely changed designs (−1% weapon use). Heat isn't what holds weapons back.
- **Faction flavours** (as you described):
  - Korath stock warships peak at a median of **97%** heat;
  - Wanderers carry almost no batteries (4%);
  - Ka'het run cool (52%), Pug and Quarg too.

  These are left out of any heat target.
- **Reading.** "Never runs hot" may mean designs stay at about 80% where stock fluctuates around and over 100%. If you
  want designs that run near the edge, that's a fire-pattern question (burst, then cool), the same lever as batteries.
  It's not a higher cap.

### 5. Stock ships under our rules

- Only 34–42% of stock warships pass our energy and heat rules, almost always failing **combat energy**.
- Shorter fights help little: 45/90 s → 45–59%.
- Primary duty dominates: 70% → 59–67%; 50% → 76–86%.
- Freighters, transports and liners pass at 67–86%; their failures are mostly the non-combat weapons rule.

### 6. Other findings

- **Anti-missile by default blocks hulls without turret mounts.** 64 of 151 base runs were "can't do this job". 31
  of them failed on the anti-missile requirement (Manta, Raven, Strong Wind, Clipper, Gypsum, Nimbo Cirrus,
  Protolith, Puffin), and many others failed on combined requirements on tiny hulls. Many stock ships have no
  anti-missile. Candidate: require anti-missile only when the hull has a turret mount, or make it a strong should.
- **Anomalous Mass stacking:** 26 of 87 designs stack it (up to 69 on the Model 128). It's the Aberrant flotsam
  outfit with +0.01 inertia reduction each. Legal in the game; does it look right to you?
- **Vulture:** every cloaking hull fails the 7 s exposure window (7+5 runs). Incoming fire assumes every weapon at
  full rate and every shot hitting: about 7,400/s at Wah Ki, 12,500/s at Mesuket, so about 52,000 health needed.
  Candidate: count a hit share of 30–50%, or the fast ships at partial duty.
- **Deviation weighting (balance):** at 0.5 designs get more even, but it moves things a lot (engine capacity use
  −16%, the KIV flips to the evasive route). Candidate default: 0.2–0.3, to judge on the review sheets.
- **Search:** 63% of solver runs hit their time limit. The class report found 30 small "search misses" (+0.001 to
  +0.027), mostly a repair module or an anti-missile turret. For final designs, use `--seconds 4` on your PC.

## Limitations of this round

- **Bad starting hulls.** Picking the lightest stock hull per class chose 5 that can't do their class role (Manta,
  Earth Shaper, Emergency Shuttle, Puffin, Scrapper). Their phase-2 re-solves were all infeasible, so phase-2 data
  covers 6 hulls: Kar Ik Vot, Shooting Star, Enforcer (combat), Argosy, Harmonikos, Melodikos.
- **Quick probes don't work.** The re-polishes from the baseline design almost never changed a design: a local
  search can't flip whole outfit classes. Full re-solves (phase 2) are what show tipping points.
- **Not swept yet:** the tail slope, the range and gun curves, and the vulture exposure model.

## Next round (needs your PC, about 2.5 hours)

Phase 3 is planned (`experiments/calibration/plan.json`). It runs the candidate settings on every hull × role that
produced a design (87), plus the anti-missile-blocked hulls without that requirement:

| Candidate | Settings |
|---|---|
| A | fights per restock 1, weapon tweaks, primary duty 70% |
| B | A + firepower 50% |
| C | B + alpha dps 15% |
| D | C + balance 0.3 |

Command, from the repo folder after `git pull`:

```
python tools/calibrate.py run --parallel 6 --alarm --keep-awake
```

Zip and upload `experiments/calibration/jobs` as before.

## What I need from you

1. **Mark the review sheets** (`aside/review/index.md`): start with the 9 starting hulls, and drill down by dimension
   where something looks off. "Looks right / plays right" per design narrows each number separately.
2. **Answer the judgement calls:**
   - fights per restock (1?);
   - opening burst and taper (alpha weight);
   - Anomalous Mass stacking;
   - the anti-missile default;
   - the vulture hit share.
3. **Run phase 3** when convenient.

---

# Round 2: phase 3 (candidate settings on every hull)

**Data.** 410 runs on your PC: the candidate settings A–D on every hull × role that produced a baseline design
(87), plus the 31 anti-missile-blocked runs without that requirement. Every run produced a design. Table:
`aside/calibration-data.md` ("Candidate settings on every hull").

**Caveat.** Phase 3 ran under the **old** combat rule (240 s dedicated / 90 s escort fights, a magazine window).
The late-mid rule (102 s fights, duty by mount, no window, the battery-less check) was built while it ran. So read
these as "which lever moves what", not as final designs.

## Combat classes (light / medium / heavy warships, interceptors), medians

| Settings | Weapon capacity used | With batteries | Battery drawdown | With secondaries | Combat heat peak |
|---|---|---|---|---|---|
| Baseline | 70% | 28% | 0% | 36% | 80% |
| A: restock 1, tweaks, primaries 70% | 74% | 38% | 33% | **86%** | 66% |
| B: A + firepower 50% | 80% | 52% | 46% | 86% | 73% |
| C: B + alpha 15% | 88% | 40% | 24% | **98%** | 75% |
| D: C + balance 0.3 | **92%** | **56%** | 40% | 98% | 78% |

## What it says

1. **Missiles: the magazine rule was the wall.** One fight per restock, plus the weapon tweaks, takes
   secondaries from 36% to 86% of combat designs (98% with alpha). Under the new rule, ammo for 1 fight
   (102 s × 79% duty) is about the same as A's (240 s × 35% window); 2 fights doubles it. So the open "fights per
   restock" question decides whether missiles appear: **1 gives missiles; 2 likely mostly doesn't.**
2. **Batteries start draining** once primaries drop to 70%: 0% → 33% drawdown under A, and 40–46% with B and D.
   The late-mid rule's shorter fight should push this further.
3. **Weapon use** rises with each lever: firepower 50% (+6 points), alpha 15% (+8), balance 0.3 (+4), reaching
   92% under D (stock warships: 82–91%).
4. **Heat** drops from 80% to 66–78%: lower duty frees heat headroom, and the levers spend some of it on weapons.
5. **Anti-missile default:** all 15 blocked combat runs work without the requirement, and under A they look like
   the others (72% weapon use, 67% with secondaries). Several hulls simply can't mount an anti-missile turret.
6. **Anomalous Mass** stacks in 19–43% of designs, most under balance 0.3. Still waiting on your call.
7. **Search:** 51–61% of solver runs hit their time limit, about as before.

## Candidate defaults (your call)

- **Fights per restock: 1.** That's what brings missiles in.
- **Firepower 50% and alpha dps 15%:** both raise weapon use without hurting anything else I can see. Alpha
  matters less now that the battery-less check and shorter fights do part of its job, so it's worth re-testing at
  10%.
- **Balance 0.3:** most weapon use and batteries, but more Anomalous Mass and a lower score. Keep it optional
  until you've looked at a few D designs on the review sheets.
- **Anti-missile:** require it only when the hull has a turret mount.

Next round: these defaults under the late-mid rule, on the same hulls.
