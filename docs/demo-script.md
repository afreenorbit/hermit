# Demo script (2:30 max)

Owner: Akshay (UI & story), with Afreen on the Switch shots. Refines plan.md §9.2.

**The one rule:** footage from the real three-laptop run and simulated footage
are never cut together as if they were the same thing. Every simulated frame
carries a visible **SIMULATION** label: the map's own badge, or a burned-in
corner watermark `SIMULATION (stand-in Switch)`. The voiceover says so too.

Legend for the **Source** column:

- **REAL**: needs the real three-laptop run ([`actual-test.md`](actual-test.md), [`switch-setup.md`](switch-setup.md) Part D).
- **SIM OK**: a labelled-simulation fallback exists and is listed.
- **ANY**: no Hermit state on screen (title cards, the README).

## Before recording

```bash
python scripts/test_gate.py          # all green, or don't record
python -m sim all --quiet            # refreshes sim/out/*
```

Have these open:

1. Three laptops (or three windows) with the critter: `pnpm --filter @hermit/critter dev`.
2. The den in Mattermost (`http://<server>:8065`) on one screen and a phone.
3. The map: `pnpm dev:map`, then `http://localhost:<port>/?journey=three_cities` in one tab and `/?live=http://127.0.0.1:47800` in another.
4. For fallback takes, a separate machine running `python -m sim live --switch standin` (ports 47801–47803, control 47804).

Recording: 1080p, cursor highlighted, captions burned in, music low.

## Shot list

| # | Time | Shot | Exact command or screen | Source | Voiceover (draft) |
|---|---|---|---|---|---|
| 1 | 0:00–0:12 | Title card, then a dead group chat ("last message: 3 weeks ago") | Static card. Mock chat screenshot with names blurred | ANY | "Friends don't drift apart only because of distance. They drift because nobody starts the conversation." |
| 2 | 0:12–0:30 | Hermit on Afreen's screen, `visiting`. Den: Hermit greets in Claude Code's voice | Critter on laptop 1. Mattermost den | REAL. **SIM OK:** `sim live --switch standin`, with the critter started as `HERMIT_KEEPER_URL=http://127.0.0.1:47801 pnpm --filter @hermit/critter dev` (no den in this take; stand-in brains only say canned lines) | "Hermit has no home. It lives on one friend's laptop at a time and uses their own AI as its brain." |
| 3 | 0:30–0:48 | Split screen: Afreen closes her lid. Seconds later Abhishek's critter goes `arriving` → `visiting`, and Hermit speaks in OpenCode's voice and says it left in a hurry | Two laptops side by side, timer overlay. Den on the phone | REAL. **SIM OK:** `curl -X POST http://127.0.0.1:47804/lid-slam/<holder>`, with two critters (`HERMIT_KEEPER_URL` set to 47801 and 47802) | "Afreen didn't say goodbye. Her laptop just closed. Switch let the soul go, and the next friend who was around picked it up." |
| 4 | 0:48–1:10 | Favor: Hermit delivers Afreen's favor, Abhishek does it from his phone, and a shell piece pops in on the critter | Den on the phone. Critter panel → Shell tab | REAL. **SIM OK (partial):** `curl -X POST http://127.0.0.1:47804/favor/<host> -H "content-type: application/json" -d '{"text":"..."}'` | "Before Hermit leaves, it asks you to leave something small for whoever's next. Doing it grows Hermit's shell." |
| 5 | 1:10–1:45 | **Under the hood.** (a) Switch Console: rooms `hermit-den` and `hermit-ledger`. (b) `!roles` in the den showing `soul` held by one brain. (c) A second brain's `assume_role` refused. (d) `@soul hi` answered by whoever holds it. (e) The ledger: a `HERMIT-CUE/1 CLAIM_SOUL` → `HERMIT-ACK/1` → `SOUL_CLAIMED` | Console and Mattermost (switch-setup D4–D6). Ledger room scrolled | REAL only. No simulated substitute for Switch's own UI. **If the real run fails:** show `docs/architecture.md` §2 (the sequence diagram) and the stand-in race test passing (`pytest keeper/tests/integration/test_switch_standin.py -q`), captioned "stand-in Switch, not real Switch" | "Switch is the whole engine. One exclusive role is Hermit's soul. Its instructions are Hermit's personality, so whoever holds it *becomes* Hermit. The room is its memory." |
| 6 | 1:45–1:55 | Lease-expiry number on screen | Caption with the D8 measurement | REAL. **Fill after the real run.** If not measured, cut this shot; never show the 8 s guess | "When a laptop vanishes, the soul frees itself in ___ seconds." |
| 7 | 1:55–2:08 | **"What if we weren't in the same city?"** The map with the SIMULATION badge, route Bengaluru → Berlin → Toronto | `http://localhost:<port>/?journey=three_cities` (plus the corner watermark) | SIM OK (this shot *is* the simulation) | "We all live in Bengaluru. The same code doesn't care. Here it is simulated across three timezones." |
| 8 | 2:08–2:14 | Back to a real critter on a real laptop | Laptop screen | REAL. **SIM OK:** cut the shot and the line | "Everything else you saw ran on our three machines." Use this line only if it is true. |
| 9 | 2:14–2:22 | Pilot numbers and one quote | From `docs/pilot-results.md` | REAL. **Fill after the pilot.** If there is no pilot, cut it and say "We haven't piloted it yet" | "In a ___-night pilot with ___ friends…" |
| 10 | 2:22–2:30 | Journey map zooming out, then the tagline | `?journey=bengaluru` from the real export, or the sample (which shows its "Sample data" banner) | REAL, or the labelled sample | "Someone is always around. Hermit makes sure that counts." |

**Running time:** 2:30. If anything runs long, cut shot 8 first, then shot 6.

## If the real run does not happen

Record the whole video from `python -m sim live --switch standin` and the
`three_cities` map. Keep the corner watermark `SIMULATION (stand-in Switch)` on
for the entire video, drop shots 5(b)–(d), 6, 8 and 9, and change the opening
line of shot 5 to: "Here is how it runs on Switch. This take uses our stand-in
server; real-Switch footage is pending." Do not imply real brains or real
laptops.

## Assets already captured

From `pnpm --filter @hermit/map capture` (sample and simulated data, labelled on
the page): `docs/assets/route-replay.gif` / `.webm`, `map-simulation.png`,
`critter-states.png`, `critter-*.png` and `postcard.png`. Use them for B-roll.
They are **not** real-run footage.
