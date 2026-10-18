# Scoring experiments: results (for review)

Branch `experiment/scoring-options`. The main branch is untouched. 234 runs overnight in the 4-CPU container:
batch 1 (180 runs) every reference × combine mode, weapon tweaks off and on; batch 2 (54 runs) three weight variants
on the three most promising references. Warship role; Kar Ik Vot 349 (heavy), Firebird (medium), Argosy (light
freighter as a warship); two runs per setting. Every design passed every check.

Each design is measured against **that hull's stock design** on raw numbers the scoring rules don't change. The
table shows medians over the three hulls (six runs), plus the Kar Ik Vot on its own, since it's the problem case.
Raw files: `experiments/batch1/`, `experiments/batch2/` (one JSON per run, `summary.md`, `report.md`).

| setting (reference / combine / weapons / weights) | raw dps × stock | weapon space vs stock | KIV raw dps | KIV shield regen | KIV hull repair | KIV route | turn | accel | speed | guns vs stock | secondaries |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **main today**: legacy / sum / plain / default | 0.61 | −7 pts | 0.60 | 2.00 | 2.15 | durable | 1.70 | 1.49 | 1.69 | −0.7 | 0 |
| legacy / sum / **tweaks** / default | 0.93 | −10 | 0.55 | 1.68 | 3.85 | durable | 2.01 | 1.54 | 3.29 | −1.5 | 0 |
| **all** / sum / tweaks / default | 0.97 | −9 | 0.60 | 1.65 | 4.03 | durable | 1.77 | 1.46 | 2.08 | −0.8 | 0.17 |
| all / sum / tweaks / **firepower 65%** | 1.03 | −7 | 0.58 | 1.40 | 4.26 | durable | 1.82 | 1.57 | 1.66 | −0.7 | 0 |
| all / sum / tweaks / **firepower 65% + evasive without speed** | 1.03 | −8 | 0.71 | 2.04 | 3.72 | durable | 2.05 | 1.44 | 1.62 | −1.2 | 0 |
| family / sum / plain / default | 0.84 | −9 | 0.83 | 0.63 | 1.40 | mixed | 1.92 | 1.85 | 3.69 | −0.3 | 0 |
| class / sum / plain / default | 0.73 | −11 | 0.79 | 0.00 | 0.15 | evasive | 1.68 | 2.05 | 3.88 | −0.8 | 0 |
| **stock** / sum / tweaks / default | 1.02 | −4 | 0.84 | **0.00** | 0.15 | evasive | 1.47 | 1.84 | 2.51 | −0.3 | 0 |
| stock / sum / tweaks / firepower 65% + evasive without speed | 1.13 | −3 | 1.05 | **0.00** | 0.15 | evasive | 1.56 | 1.44 | 1.71 | 0.0 | 0.17 |
| legacy / **power:0.5** / plain / default | 0.67 | −10 | 0.47 | 1.74 | 5.89 | durable | 1.71 | 1.49 | 3.26 | −1.3 | 0 |
| all / **power:0** / tweaks / default | 0.68 | −9 | 0.53 | 2.11 | 3.66 | durable | 1.99 | 1.51 | 2.31 | −1.2 | 0 |

All 30 settings from batch 1 are in `experiments/batch1/summary.md`; batch 2 is in `experiments/batch2/summary.md`.

## What the numbers say

1. **The weapon tweaks are the biggest single win.** These are the homing exemptions plus straight-line gun and range
   curves. With the same scoring, raw damage goes from 0.61× to 0.93× stock (legacy ladder) and from 0.74× to 0.97×
   (all ships). I see no cost elsewhere.
2. **Excluding Superheavy, Unclassified, Unclassified Minor and Game Mechanics ("all") helps a little and costs nothing.**
   Class-based ladders ("family", "class") were *not* better. A strong design still beats nearly its whole class, so
   it sits at the top of the ladder again. They also made scoring noisier (bigger run-to-run spread).
3. **"Stock" scoring (improvement over the hull's stock design) gives the most firepower, but it breaks the tank.** In
   every run the Kar Ik Vot goes evasive with **zero shield regen**, buying torch speed instead (2.5× stock). Not
   usable as it stands. The log scale makes large speed multiples cheap.
4. **The balance setting (power means) made things worse.** It lifts the weakest metrics, which on these ships are
   mobility on the tank, anti-missile and pull, not weapons. I'd drop it, or revisit it once the weights are right.
5. **Weights help only a little.** Firepower at 65%, and an evasive branch without top speed, add a few percent of raw
   damage. They don't close the gap.
6. **The real cap on firepower is the sustained-fire rule, not the scoring.** Stock ships are not built to it. The
   stock Kar Ik Vot settles at 104% heat and runs −1,109 energy/s with everything firing; the stock Firebird at 105%
   and −143/s. Both rely on batteries and on not firing everything all the time. The Argosy passes. Every design here
   must fire all weapons continuously at ≤ 90% heat and non-negative energy (your decided rule for combat ships), so it
   cannot carry the stock ship's raw weapon load. Designs give power and cooling about the same share of outfit space
   as stock (21–31%), so the gap is the rule, not wasted space.
7. **Mobility is consistently 1.4–2× stock and speed 1.4–5× stock, under every setting.** That's torches with drag
   reduction and their fuel and power. It's where the "other" outfit space goes on evasive designs.
8. **Secondary weapons still almost never appear,** even with the homing exemptions. What's left against them is the
   magazine window (they count for 35% of a fight) and the space for two fights' worth of ammunition. That needs its
   own change.

## Recommendation

- **Adopt on main:** reference `all` (drop the outlier classes from every ladder) and the weapon tweaks. Keep `sum`.
  Optionally firepower 65% for the warship.
- **Your decision, the biggest lever left:** the sustained-fire rule for combat ships. Options:
  1. **Keep it.** Designs will always carry less raw firepower than stock, but can fire forever.
  2. **Battery-backed bursts.** Allow an energy (and heat) deficit if batteries and heat capacity cover it for the fight
     length (90 s escort, 240 s warship). This is how stock ships work.
  3. **Firing shares.** Count guns firing about 60% of the time and turrets about 85% (your earlier note) for energy and
     heat, while still requiring a sustainable balance.
- **Then:** secondaries (the magazine window and ammo space), and the gun curve after your in-game testing.
- **Not recommended:** class ladders, stock scoring as it stands, power means.

## Trying it

```bash
git checkout experiment/scoring-options
es-optimizer optimize "Kar Ik Vot 349" --role warship --reference all --weapon-tweaks
es-optimizer optimize "Kar Ik Vot 349" --role warship --reference all --weapon-tweaks --emphasize firepower=0.65
python tools/experiment.py --home ~/.local/share/es-optimizer --out runs/exp --runs 2 --tweaks on --references all,stock --combines sum
python tools/experiment_analyse.py runs/exp
```
