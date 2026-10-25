# War-zone observation: how stock NPCs actually fight (fleet against fleet)

**What this is.** Your idea: watch stock NPC fleets fight in hot systems, headless, and measure what a fight looks
like. A fight is **fleet against fleet**, as you defined it. One fleet's fight runs until it gets a 10 s breather,
so it can be against several fleets at once or back to back. That's the player's case.

This is one signal for the calibration numbers, not a target. NPC AI isn't a player, and NPC ships never restock.

**Data.**
- 30 runs, 1,440 game minutes in all: 8,464 fleet fights and 23,865 ship records.
- Ten systems, each run 3 times:
  - **Human war zones** (pirates vs militia, merchants, Republic, Syndicate): Nunki, Shaula, Lesath, Beta Lupi
    and Almaaz at 30 game minutes per run; Misam, Durax and Polaris, which also get Korath raids, at 90.
  - **Alien war zones:** Wah Ki (Hai vs Hai Unfettered) and Mesuket (Kor Mereti vs Kor Sestor), 30 minutes per run.
- Tables: `experiments/warzone/summary.md`. Per-fight records: `experiments/warzone/fights.json`. Method:
  `tools/warzone/README.md`.
- Game build: 0.11.2 with a logging-only patch, in a separate source copy.

## Fleet fights

**Enemy fleets (your question).** "Opposing fleets" counts the enemy side only. "At the same time" is the most
enemy fleets engaged at one moment.

| Human war zones | Fights | Length | Own ships | Enemy ships | Own ships lost |
|---|---|---|---|---|---|
| 1 enemy fleet at a time | 2,540 | 14 s (9–22) | 1 (1–2) | 2 (1–4) | 32% |
| 2 at the same time | 2,035 | 20 s (12–36) | 1 (1–2) | 5 (3–7) | 55% |
| 3+ at the same time | 1,484 | 30 s (15–56) | 2 (1–3) | 9 (6–13) | 68% |

- In human systems, about 42% of fights are against one enemy fleet at a time, 34% against two and 24% against
  three or more. Fleets are small: one or two ships.
- The alien zones are much bigger: a median of 28 enemy ships in Wah Ki fights, 42 in Mesuket. Nearly every fight
  there is against 3+ fleets.

## Ships in fights (human war zones), medians

| Class | Time in fight | Gun duty | Turret duty | Secondary duty | Ammo per fight | Fights of ammo | Energy low (worst 10%) | Heat peak (top 10%) |
|---|---|---|---|---|---|---|---|---|
| Light Warship | 16 s | 32% | 23% | 81% | 41% | 2.4 | 98% (95%) | 51% (71%) |
| Medium Warship | 22 s | 25% | 28% | 79% | 29% | 3.0 | 99% (91%) | 43% (64%) |
| Heavy Warship | 28 s | 25% | 27% | 67% | 30% | 2.5 | 100% (100%) | 30% (62%) |
| Interceptor | 16 s | 16% | – | 57% | 43% | 1.5 | 100% (93%) | 25% (55%) |
| Light Freighter | 18 s | 18% | 32% | 71% | 62% | 1.4 | 100% (98%) | 25% (62%) |

**Wah Ki (Hai):** warships fire guns 31–50% and turrets 32–49% of the time, and secondaries about 90%. They use
37–46% of their ammo per fight. Energy stays above 90% in the median fight; the worst 10% drop to 72–87%. Heat
peaks around 40–50%. Unfettered ships retreat a lot: about 89% of them jump out at about 45% health.

**Mesuket (Kor drones): the outlier.**
- Warships fire guns 66–73% and turrets 63–70% of the time.
- Median low energy is 48–85%, and the worst 10% run **empty**.
- Heat peaks at 85–91% (top 10%: 97–100%).
- They fight until they're destroyed or disabled.

That's a different machine: automata built to fight flat out.

## Reading it

1. **The player's case.** A typical human-space fight is 1–3 small fleets at once, lasting **15–30 s**, or up to
   about a minute in the bigger clashes. Our rule assumes one 240 s fight at full fire.
2. **Duty depends on mount type.** In human space, guns and turrets fire about 25–30% of a fight, counting the time
   spent closing in. Hai fire more (30–50%); Kor drones 65–73%. Secondaries fire at about 80% while ammo lasts,
   about what our rule already assumes.
3. **Energy only runs out for the Kor.** Human and Hai ships finish fights with most of their battery. Kor
   warships run dry. So "energy runs out before heat does" is a Kor trait in stock data, not a human one.
4. **Ammo.** A fight uses about 30–40% of a warship's magazine: 2.5–3 fights' worth by the observed fight, against
   0.83 by our 240 s rule.
5. **Heat.** Human warships peak at 30–50% (top 10% about 62–71%). Kor and Korath run hot (top 10% at 96–100%),
   the flavour you described.
6. **Retreats.** Human ships retreat in 13–24% of fights, at about 25–65% health. Hai Unfettered retreat almost
   always, at about 45%.

## Game stages (your framing)

The three war-zone types are three stages of the game, not one average:

- **Beginner:** human space vs pirates. Small, frequent pirate fleets: what a new player runs into.
- **Early mid game:** Hai (Wah Ki). Bigger fights; expect a better-equipped player.
- **Late mid game:** Kor (Mesuket). Flat-out automata; the player is better equipped still.
- **Late game: not observable.** Most alien battles are everyone-hostile-to-the-player, with no other government
  flying ships there, or are gated by story flags. So there are no NPC-vs-NPC fights to watch. Any late-game model
  is an extrapolation and will be labelled as one.

**Default: late mid game** (your call). Unless a design says otherwise, the optimizer designs for the Kor-style
fight; beginner and early mid are opt-in.

So the fight model should be **per stage**, chosen per design. A beginner ship isn't sized for Kor-style fights,
and a late-mid ship isn't judged by pirate skirmishes. The observed numbers are how the **opponents** fight at
each stage. The player's ship should out-sustain them, so its duty and fight chain sit at or above them. Recorded
in `docs/design-notes.md` ("Combat by game stage").

## Candidate changes this suggests (your call)

- **Fight model:** a chain of 1–3 short fleet fights, about 15–30 s each with no breather, in place of one 240 s
  fight. That covers about 45–90 s of fire.
- **Separate gun and turret duty:** about 30–40% for a player, a bit above the stock human 25–30%, since a player
  aims deliberately. Use the Hai's 40–50% as a "hard fight" setting.
- **Magazine:** size it from that chain at 80% secondary duty, for 2 chains between restocks (or 1). Missiles
  would come in on far more hulls.
- **Per-stage fight models:** beginner (human: 1–3 fleets, 15–30 s each, 30–40% duty), early mid (Hai: 30–50 s,
  40–50% duty), late mid (Kor: 40 s+, about 70% duty, energy allowed to run low).
- **Retreat health about 50%,** for anything that needs a "fight until X" (recovery, vulture exposure).

## Limits

- **Duty includes closing in.** A player with long-range weapons who stays in range may fire more.
- **Fleets are linked by their leader.** A fleet whose leader dies may later count as a new fleet, which slightly
  inflates the number of opposing fleets in long brawls.
- Space Liners in Wah Ki show 0% heat (the Hai liner hulls); that looks like a quirk of those hulls, not a bug.
