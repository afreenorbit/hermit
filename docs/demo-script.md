# Hermit demo script (2:30)

Use [the three laptop runbook](running-on-three-laptops.md) before recording. Keep the keeper and Switch Console visible enough to show that the action is real. The labels **REAL**, **SAMPLE**, and **SIMULATION** must remain on screen whenever footage changes source.

## Recordable story today

| Time | Screen and action | What to say | Evidence |
| --- | --- | --- | --- |
| 0:00–0:15 | Three friends' laptops, each with the colored Hermit mascot. Show names above the mascot. | "We are often online at different times. Hermit gives us a small way to find one another." | REAL when all three machines are connected. |
| 0:15–0:35 | Afreen's panel and live map. Press **Bring Hermit here**. Show Afreen as holder on all screens. | "Each keeper senses whether its laptop is around. Switch carries the shared claim and presence events." | REAL. Capture `/v1/group/status` alongside the map. |
| 0:35–0:55 | In Afreen's Quest tab, leave a small favor. Show it marked as carried. | "A visit can leave something for the next friend, like a song or a tiny creative prompt." | REAL. The favor is written to the Switch ledger. |
| 0:55–1:15 | Afreen presses **Send Hermit on**. Akshay or Abhishek claims when awake. Show departure, arrival, and the name changing on all screens. | "When a friend is away, Hermit can visit someone who is present." | REAL only if both screens and the ledger agree. Measure elapsed time; do not invent a latency. |
| 1:15–1:35 | New holder opens Quest, completes the carried favor, then opens Shell. | "Completing a favor adds a piece to our shared shell. It remembers things we actually did together." | REAL. Check the new piece on two laptops. |
| 1:35–1:50 | A non-holder opens Friends and sends the current holder a note. Show it arriving in the holder's Log. | "You can send a short message to the friend Hermit is visiting without keeping a group chat open." | REAL. The note travels through Switch events. |
| 1:50–2:10 | Switch Console: keeper agents, `hermit-den`, `hermit-ledger`; then unplug Switch briefly and show the keeper report it offline. | "Switch is our shared transport. Without it, these laptops cannot agree where Hermit is or pass the favor and note." | REAL. Restore Switch and show recovery. Do not show private keys. |
| 2:10–2:22 | Journey map with its source badge visible. | "The map lets us revisit the journey. This three city view uses sample data." | SAMPLE. If showing a live export, use its actual source label. |
| 2:22–2:30 | The two or three live mascots together and closing line. | "A little visitor made an asynchronous friendship feel less distant." | REAL. |

## If the other laptops are offline

Record only the local claim, favor, and Switch failure/recovery. Use the captured [live presence](assets/live-presence-afreen.png) and [live Quest](assets/live-quest-afreen.png) images as real one laptop evidence. The [route replay](assets/route-replay.webm) and `?journey=three_cities` are **SAMPLE/SIMULATION** material. A simulation may explain the handoff, but it cannot be described as a completed three laptop test.

## Important wording

The current live configuration is `keeper_claimed`: it coordinates a **provisional** holder through Switch ledger events. It does not prove a server enforced exclusive `soul` role or a coding agent speaking as Hermit. The `agent_instructed` path exists in code but is a separate, unverified live gate. Keep this distinction in the voiceover, on screen, and in the submission. The [blog](blog.md) explains both paths.

## Capture checklist

1. Record Edge or the Hermit app. Keep Codex, ChatGPT, passwords, API keys, and unrelated windows out of frame.
2. Show the clock or timer during a measured handoff. Report only the measurement observed.
3. Show each participant's consent before using their name, voice, screen, or messages publicly.
4. Use `python scripts/test_gate.py --quick` before recording, then run the full gate for submission.
5. Keep the source badge visible on sample and simulated footage. Never splice it into a real sequence as though it were the same run.
