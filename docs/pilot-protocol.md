# Pilot protocol

Owner: Abhishek (recruiting, numbers), Afreen (setup). Plan §10.6.

The pilot is our impact evidence. It is small and run with friends of the team,
and the write-up says so. Its job is to show what actually happened when Hermit
ran on real laptops, not to prove a claim.

## When and who

- **When:** Nov 6 evening → Nov 7 morning. One night and a day.
- **Hosts (run a keeper):** Afreen, Abhishek, Akshay. Add anyone else who runs
  `python -m hermit_keeper check` successfully before 18:00 on Nov 6.
- **Den members (no keeper needed):** 2–6 friends, who join the den from Discord
  or Mattermost on any device.
- **Optional remote host** (plan §10.6b): a bonus, never a dependency. Nothing
  below assumes they turn up.

## Consent (post this in the den before starting)

> Hey! For the next day Hermit, a small creature, will move between our laptops
> and talk to us here. What gets logged: when Hermit moves, the favors you leave
> and do, and your area (e.g. "Kengeri", never an address). Nothing from anyone's
> files ever leaves their laptop. Hermit only sees file *counts* in one folder
> you chose. Say "Hermit, mute" any time, or just leave. We'll share the numbers
> and ask 3 quick questions tomorrow. Reply 👍 if you're in.

Only count people who replied 👍.

## Setup checklist (each host, by 18:00 Nov 6)

- [ ] `pip install -e "keeper[dev]"` and `python -m hermit_keeper check` both pass.
- [ ] `hermit.config.toml` has your real `host_id`, area-level city, `Asia/Kolkata`
      timezone, and your real bedtime.
- [ ] `~/HermitWindow` exists (may be empty).
- [ ] The keeper runs and `python -m hermit_keeper status` answers.
- [ ] The critter shows on your screen.
- [ ] Your clock is synced (Settings → Time → Sync now). Handoff latency is
      measured across laptops.

## What we measure

All of it comes from the ledger. Nothing is self-reported except the survey.

| Measure | Source |
|---|---|
| Handoffs | `ARRIVAL_ANNOUNCED` lines |
| Handoff latency p50/p95 (graceful vs abrupt) | release → next arrival |
| Favors left / completed, completion rate | `FAVOR_LEFT`, `FAVOR_COMPLETED` |
| Median time to complete a favor | `FAVOR_ASSIGNED` → `FAVOR_COMPLETED` |
| Shell pieces grown | `SHELL_PIECE_ADDED` |
| Departures by kind | graceful / bedtime / abrupt / manual |
| Bedtime evictions | `departure: bedtime` |
| Overlaps suggested vs taken (if `features.overlap` is on) | `OVERLAP_SUGGESTED` + next-day den check |
| "Nobody home" time | gaps between stops |

## Collecting the data (Nov 7, 09:00)

Each host's keeper mirrors its events to `~/.hermit/journey.jsonl`. Together
those files are the whole ledger, so merging them rebuilds the journey even if
the room's history is gone.

1. Each host sends their `~/.hermit/journey.jsonl` to Abhishek. It holds event
   lines only: no file names, no messages.
2. Merge and export:

   ```bash
   python scripts/export_journey.py \
     --from-files afreen.jsonl abhishek.jsonl akshay.jsonl \
     --hosts pilot-hosts.json \
     --out docs/pilot/journey.json
   ```

3. Compute the numbers (`python -m sim metrics`, once the metrics PR is merged):

   ```bash
   python -m sim metrics docs/pilot/journey.json
   ```

4. Copy the table into `docs/pilot-results.md`. **Label it as real pilot data,
   and never mix in simulation numbers.**

## Survey (Google Form, sent Nov 7 morning, 3 questions)

1. Did Hermit get you to talk to or do something for a friend you otherwise
   wouldn't have this week? *(Yes / Maybe / No)*
2. Would you keep Hermit running for a month? *(1–5)*
3. Did Hermit feel different on different laptops? What did you notice?
   *(free text)*

Ask permission before quoting anyone by name. Otherwise quote them as "a friend".

## Clips to capture during the pilot

- A real handoff: the critter leaving one screen and arriving on another.
- A favor answered from a phone, and the shell piece appearing.
- A bedtime goodbye.

## Stop rules

- Any P0 (two souls, a lost soul that never recovers, data leak from a window
  folder): stop the pilot, fix it, restart, and record that it happened.
- Anyone says "mute" or leaves: respect it immediately and keep going without them.
