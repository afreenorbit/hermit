# Running Hermit on three laptops

Owner: Afreen. What actually runs today, and what does not.

## The short version

Each laptop runs **its own keeper and its own critter**. The critter talks only
to the keeper on that machine (`127.0.0.1`). Every laptop shows a mascot, not
just the one hosting Hermit.

Two different ideas, kept apart everywhere in the code:

| | decided by | one answer or three? |
|---|---|---|
| **Who holds the soul** | the shared Switch lease | one, for the whole group |
| **Whether a laptop can host** | that machine's own keyboard and mouse | three, independent |

Merging those two is how you get two laptops both showing *visiting*.

## What each mascot means

| Mood | When |
|---|---|
| **visiting** | this laptop holds the soul (only ever one laptop) |
| **arriving** | this laptop *won* the claim, for the first 10 s |
| **away** | leaving, or just left |
| **sleeping** | this host is idle, or past their bedtime |
| **waiting** | this laptop is awake; Hermit is with someone else |
| **offline** | we cannot reach this keeper — stated, not guessed |

`arriving` deliberately follows a **successful claim**, not an attempt. When a
soul frees, every awake laptop reaches for it at once; showing them all
*arriving* would have Hermit apparently landing in two places.

## Today: one machine, three keepers

This is what works right now, and it is a real test of the handoff and the
one-soul invariant.

```bash
python -m sim live
```

Three keepers share **one** lease and **one** ledger, on three ports:

```
afreen    http://127.0.0.1:47801   (claude-code)
abhishek  http://127.0.0.1:47802   (opencode)
akshay    http://127.0.0.1:47803   (codex)
```

Drive presence by hand:

```bash
curl -X POST http://127.0.0.1:47801/v1/presence/override -H "content-type: application/json" -d '{"mode":"asleep"}'
```

> **Why not just start three keepers in `fake` mode?** Each would build its own
> `FakeSoulLease`, so all three would believe they hold the soul and all three
> critters would show *visiting*. That is three unrelated programs, not a demo.

**What this does not test:** the network, the Switch client, or one laptop's
keeper dying while the others keep running — all three keepers share a single
process here, so they stop together. Those need real Switch.

## Today: one laptop, for real

A real keeper on your own machine, driven by your actual keyboard:

```bash
cp hermit.config.example.toml hermit.config.toml
```

```bash
python -m hermit_keeper check
```

```bash
python -m hermit_keeper run
```

Presence is genuine — `GetLastInputInfo` on Windows, `ioreg` on macOS,
`xprintidle` on Linux. Stop typing for `idle_threshold_s` and the keeper really
does notice.

Then the critter, pointed at that keeper:

```bash
pnpm --filter @hermit/critter dev
```

## The dashboard

```bash
pnpm dev:map
```

Vite picks the first free port from 5173 upward and **prints the real one** —
read it from the terminal rather than assuming. Open it with a keeper to get
live status:

```
http://localhost:<printed-port>/?live=http://127.0.0.1:47801
```

Without `?live=` the page is the journey alone: history, from an exported JSON
file. The page says so under the panel. **The critter does not need this page
open** — it talks to its own keeper.

Only loopback origins are accepted in `?live=`, so a link you share cannot make
someone else's browser probe your network.

### Publishing it

`pnpm --filter @hermit/map build` produces a static `map/dist/`. Any static
host serves it (GitHub Pages, Netlify, `npx serve map/dist`). Two caveats:

- A published page cannot reach anyone's `127.0.0.1` keeper, so **live status
  only works locally**. Published, it is the journey page.
- `map/public/data/journey.json` is git-ignored and generated. Copy one in
  before building, e.g. `cp sim/out/one_timezone_day/journey.json
  map/public/data/journey.json`, or the page falls back to the committed
  sample.

## Three real laptops

**Not run yet.** The plan is one Switch server on Afreen's laptop, reached
over Tailscale. Follow [`switch-setup.md`](switch-setup.md) for the server,
Switch Console and the rooms, then [`actual-test.md`](actual-test.md) for the
test itself. In short:

1. Bring up Switch. `python switch/scripts/bootstrap_rooms.py` registers the
   keepers and creates both rooms over HTTP. The `soul` role must be defined
   by a connected brain, and `--dry-run` prints the exact call.
2. Each laptop sets `lease_strategy = "agent_instructed"`,
   `switch.server_url`, `switch.agent_id` and `[switch.rooms]`, and exports
   its token: `export HERMIT_SWITCH_TOKEN=...`
3. `python -m hermit_keeper check --switch`, then `python -m hermit_keeper run`
   on each.

The keeper never claims the soul itself — it cues the brain, which calls
`assume_role("soul")`, because no external path can assume a role on an
agent's behalf (`docs/switch-facts.md` SP2).

**What is proven.** Against a real `switch-v0.9.0`, the Switch client
registers, posts, and receives another keeper's ledger line. The full
`agent_instructed` path (claims, lid slam, outage, favors) is proven only
against `sim/switch_standin.py`, a stand-in. Try it on one machine with
`python -m sim live --switch standin`. Real role exclusivity with real brains
and the real lease-expiry time are still open (switch-facts "Still open").
`python -m hermit_keeper check --switch` prints what is settled and what still
needs a live session.

## Verified

With the live harness, a handoff from Akshay to Afreen while Abhishek is online:

| | afreen | abhishek | akshay | holder |
|---|---|---|---|---|
| before | waiting | waiting | **visiting** | akshay |
| +4 s | waiting | waiting | **away** | akshay |
| +8 s | waiting | waiting | sleeping | free |
| +20 s | **arriving** | waiting | sleeping | afreen |
| +28 s | **visiting** | waiting | sleeping | afreen |

Never two *visiting*, never two *arriving*.

Keeper killed with the dashboard open: the panel keeps the last snapshot, flips
to “Cannot reach the keeper”, and recovers on its own when the keeper returns —
no reload.
