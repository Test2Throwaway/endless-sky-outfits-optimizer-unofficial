# War-zone observation, round 1: how stock NPCs actually fight

**What this is.** Your idea: watch stock NPC fleets fight in hot systems, headless, and measure what a fight looks
like: ammo per fight, weapon duty, energy and heat, fight length, retreats. This is one signal for the
calibration numbers, not a target. NPC AI isn't a player, and NPC ships never restock.

**Data.**
- Systems: Nunki, Shaula, Lesath, Beta Lupi and Almaaz at 30 game minutes each; Misam, Durax and Polaris (the Korath
  raid systems) at 90 minutes each. Each system ran 3 times, so 1,260 game minutes in total.
- That gives 11,021 ship-fights, cut per ship (a fight ends when the ship is disabled or destroyed, jumps out, or
  stops fighting for 10 s).
- Tables: `experiments/warzone/summary.md`. Per-fight records: `experiments/warzone/fights.json`. How it works:
  `tools/warzone/README.md`.
- Game build: 0.11.2 with a logging-only patch, in a separate source copy. Your game folder and the game repo were
  not touched.

## What it says

| Question | Warships (light / medium / heavy), medians | What our rules assume |
|---|---|---|
| Fight length, per ship | 16 / 22 / 28 s (quartiles 10–56 s); only 10% of warship fights last 60 s or more | 240 s (dedicated), 90 s (escort) |
| Primary weapon duty | 33% / 28% / 26% of the fight; still 26% in fights of 60 s or more | 100% (70% in phase-3 candidates) |
| Secondary duty, while it has ammo | 78% / 81% / 67% | 80% in the magazine window |
| Ammo used per fight, as a share of full | 43% / 31% / 42% | – |
| Fights of ammo carried | 2.2 / 2.9 / 2.0 | 2 fights (phase 3 candidates: 1) |
| Energy low point | 98–100%; worst 10% of fights 90–95% | Must cover the whole fight |
| Heat peak | 51% / 44% / 31%; top 10% at 62–71% | 90% cap |
| How fights end | about 30% destroyed, 19% disabled, 6–9% retreat, about 21% leave | – |
| Health at retreat | 48–72% (quartiles about 25–85%) | – |

## Reading it

1. **Fights are short and intermittent.** A stock NPC warship fires its main guns about a quarter to a third of a
   fight's time, counting the time spent closing in and turning. That's far below the 100% the combat rule
   assumes. It fits the calibration finding that stock ships pass our energy rule far more often at 50–70%
   primary duty.
2. **Energy is never the limit for NPCs.** Batteries barely move: the worst 10% of fights still end at 90%+.
   NPC loadouts aren't built for sustained fire. They fire in bursts and stop. So "no batteries" in our designs
   isn't explained by NPC habits. It's still the burst question: what's a full opening worth?
3. **Secondaries get fired hard when carried.** About 80% duty while ammo lasts, and 89% of warship fights that
   carry secondaries use some. A fight uses about a third to a half of the magazine, so NPCs carry about 2–3 of
   their own (short) fights' worth. The calibration said stock carries 0.83 fights' worth by **our** rule: that's
   because our rule's fight is 240 s, about 10× the observed fight.
4. **Heat.** NPCs run cool in practice (median peak 30–50%). Korath push their top 10% to 91%, the flavour you
   described.
5. **Retreats** happen at about half health, 6–13% of fights; Korath retreat late (about 24% health).

## Candidate changes this suggests (your call)

- **Primary duty 30–50%** for the combat rule, or a shorter fight at a higher duty. Observed is about 30%; a player
  fires more deliberately than the AI, so somewhat higher.
- **Fight length.** Per-ship fights are 15–30 s, but a player fights several in a row before recovering. One option:
  the rule's fight = 3–4 observed fights at observed duty, so the energy over that span matters, not a single
  4-minute slugfest.
- **Magazine:** size it from observed use: a fight uses about 40% of a stock magazine, at 80% duty for about
  20 s. "Two fights' worth" by that measure is far smaller than today's 240 s rule, which would let missiles in.
- **Retreat health about 50%** if a "fight until X" assumption is ever needed (e.g. recovery or vulture exposure).

## Limits

- **Per-ship fights, not battles.** A battle in a system lasts longer than any one ship's part in it. If you want
  battle length too, I can cluster ships by time and place.
- **Duty counts the approach.** AI ships spend time closing in; a player with long-range weapons may differ.
- **No Hai, Wanderer or other alien fleets yet.** Wah Ki and Mesuket (the vulture war zones) would add Hai and Kor
  Mereti/Sestor fights if you want them.
- The "left" share includes ships that finished fighting and flew on; only jumps at under 95% health count as
  retreats.
