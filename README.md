<h1 align="center">Hermit</h1>

<p align="center">
  <strong>A small creature with no home of its own.</strong><br>
  It lives on one friend's laptop at a time and uses that friend's AI agent as its brain.<br>
  When they go idle, it moves to someone who's awake.
</p>

<p align="center">
  Built for <a href="https://www.wemakedevs.org/hackathons/switch">Flip the Switch</a>
  (WeMakeDevs × DevTools Academy × Switch) · <strong>Track 02 — Best Personal or Creative Workflow</strong>
</p>

---

## What it is

You don't drift apart from your friends because you're far away. You drift apart
because **nobody starts it.** The group chat has been quiet for three weeks and
everyone has noticed.

Hermit starts it. Exactly one friend "has" Hermit at any moment — because exactly
one agent holds the `soul` role in Switch. When that friend's laptop goes idle,
the role frees and Hermit moves to whoever is around next, speaking through
*their* coding agent instead. Its memory is the Switch room, so it remembers what
you said last night while speaking in someone else's voice this morning.

**Hermit follows attention, not daylight.** Across timezones that means someone
is always awake. For us — three friends in Bengaluru, 25 km apart, who still
manage not to see each other for weeks — it means someone is always free: one in
class, one commuting, one up at 2am.

Before it leaves, Hermit asks its host to leave a **favor** for whoever it visits
next — a Switch room Task. Doing the favor adds a piece to Hermit's **shell**,
generated from the hour it arrived, which brain voiced it, how long it stayed and
how it left. Over a week the group gets a journey map and a shell they built
together.

> **Status: Phase 1.** The scaffolding, contracts and fakes are in. The features
> are being built against them. See [`plan.md`](plan.md) for the full build plan.

## Why Switch is the whole engine

Not a chat transport we could swap out — remove any row below and Hermit stops existing.

| Switch feature | Hermit mechanic |
|---|---|
| **Exclusive leased role** | **The soul.** Only one Hermit exists at a time, enforced by Switch, not by us. |
| **Lease expiry on session stop** | Lid slams shut → the soul frees itself → Hermit moves on even though nobody said goodbye. |
| **Room history & knowledge** | Hermit's memory survives the brain changing underneath it (Claude Code → Codex → OpenCode). |
| **Room rules** | Hermit's identity, voice and the bedtime rule live in the room, not in our code. |
| **Room tasks** | Favors, assigned to the next host, completed from a phone. |
| **Bridges (Discord)** | Friends play from wherever they already talk. |
| **Agent Protocol** | Our keeper is a custom agent sitting beside off-the-shelf coding agents in the same room. |
| **BYO agent, self-hosted** | No central AI bill and no vendor holding the group's messages. |

**What breaks without Switch:** everything. There is no "one Hermit" without an
exclusive lease, no memory across brains without room history, and no favors
without room tasks.

## Architecture

```
                    ┌──────────────────────────────────────────────┐
                    │                SWITCH SERVER                 │
                    │  Room: hermit-den   <- Discord bridge        │
                    │    rules · knowledge · tasks (favors)        │
                    │    role: soul  (EXCLUSIVE, leased)           │
                    │  Room: hermit-ledger  (machine log/control)  │
                    └───────▲──────────────▲──────────────▲────────┘
                            │              │              │
          ┌─────────────────┴────┐  ┌──────┴───────────┐  ┌───┴──────────────┐
          │ LAPTOP: afreen       │  │ LAPTOP: abhishek │  │ LAPTOP: akshay   │
          │  brain: Claude Code  │  │  brain: OpenCode │  │  brain: Codex    │
          │  keeper (Python)     │  │  keeper          │  │  keeper          │
          │  critter (Electron)  │  │  critter         │  │  critter         │
          └──────────────────────┘  └──────────────────┘  └──────────────────┘

          Journey map (web) <- journey.json exported from hermit-ledger
```

Two agents per laptop: the **brain** is the friend's own off-the-shelf coding
agent (it gives Hermit a voice and can see only a folder they chose to share);
the **keeper** is our Python process (presence, the soul lease, the state
machine, the ledger, the critter's API). Full detail in [`plan.md`](plan.md) §3.

### The three laptops

| Host | `host_id` | Brain for Hermit | Fallback installed |
|---|---|---|---|
| Afreen | `afreen` | **Claude Code** | OpenCode, Codex |
| Abhishek | `abhishek` | **OpenCode** | Claude Code |
| Akshay | `akshay` | **Codex** | Claude Code |

All three in Bengaluru, same timezone. Handoffs come from work, class, commutes
and different sleep hours rather than from daylight — rarer, and we report the
real number. `sim/scenarios/three_cities_day.yaml` runs the identical code with
three timezones to show the scattered-group case; it is labelled as a simulation
wherever it appears.

One brain each, all three different — so Hermit's memory visibly survives the
agent changing underneath it. That's the demo. If a brain won't join a room
during the pilot, that host falls back to Claude Code and we say so in the
README; only their `brain_provider` line changes.

## Repo layout

| Path | What's in it | Owner |
|---|---|---|
| `shared/schemas/` | **The contracts.** Frozen after Phase 1 — changes need two approvals. | A |
| `switch/` | Room template, rules, knowledge files, bootstrap script | A |
| `keeper/` | The Python keeper: presence, lease, state machine, local API | A + B |
| `sim/` | Three hosts on one machine, time compressed. What judges run. | D |
| `ui-shared/` | `@hermit/ui` — pixel design system, shell renderer, formatters | C |
| `critter/` | Electron desktop creature | C |
| `map/` | The journey map (Vite + React) | C |
| `docs/` | Switch findings, architecture, pilot, demo script | D |
| `plan.md` | The full build plan. **Read this before you start.** | all |

Roles: **A** Switch & core · **B** gameplay · **C** UI · **D** sim, QA & story.
With three people, D splits between B and C. `.github/CODEOWNERS` encodes it —
put your real handles in there before protecting `main`.

## Getting set up

You need **Python 3.11+**, **Node 20+**, and **git**. Docker only when you start
on real Switch (Phase 2) — everything before that runs on fakes.

### 1. Clone and branch

```bash
git clone <repo-url> hermit && cd hermit
```

```bash
git checkout -b feat/<area>-<short>
```

### 2. Python keeper (venv)

macOS / Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e "keeper[dev]"
```

Windows (PowerShell):

```powershell
py -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e "keeper[dev]"
```

Check it:

```bash
pytest keeper -m "not live" -q
```

### 3. Node workspaces

`corepack` ships with Node, so you don't need a global pnpm install:

```bash
corepack enable pnpm && pnpm install
```

Run the map:

```bash
pnpm dev:map
```

Vite prints the port it actually chose (5173 if free, otherwise the next one) —
read it from the terminal. It reads
`map/public/data/journey.sample.json` — a fake 8-stop journey with every
departure type in it, so the UI can be built before any of the backend exists.

Two fixtures ship, both valid against the same schema, because the map has to
auto-fit to either:

| Fixture | Scale | For |
|---|---|---|
| `journey.sample.json` | Bengaluru, 3 areas ~25 km apart | our real pilot shape |
| `journey.wide.sample.json` | Bengaluru / Berlin / Toronto | the scattered-group case |

Regenerate both with `python scripts/make_fixtures.py`.

### 4. Your host config

```bash
cp hermit.config.example.toml hermit.config.toml
```

Edit your `host_id`, city, timezone and brain. **This file is git-ignored and
must stay that way** — tokens live in environment variables, never in the file.

```bash
python -m hermit_keeper doctor
```

## How we work

Everyone builds against the contracts in `shared/schemas/` and the fakes in
`keeper/hermit_keeper/*/fake.py`. **Nobody waits for real Switch to work.**

- **Branches:** `feat/<area>-<short>`, `fix/<area>-<short>`, `docs/...` off `main`.
- **Stay in your folders.** Need something elsewhere? Small PR to that owner.
- **Contracts are frozen** after Phase 1: a change to `shared/` needs two role owners.
- **PRs:** around 400 lines or fewer, one concern, 1 review + green CI, squash merge.
- **Merge twice a day** (≈13:00 and ≈22:00 IST). Never sit on a branch over 12 hours.
- **Commits:** conventional — `feat(keeper): add sleep-gap detection`.

The PR template asks which files are AI-generated and whether you've read every
line. Answer it honestly — it's there so we don't merge code nobody can explain.

### Commands

| Command | What it does |
|---|---|
| `pytest keeper -m "not live" -q` | Keeper tests (no Switch needed) |
| `ruff check keeper` | Lint |
| `pnpm -r typecheck` / `pnpm -r test` | UI types and tests |
| `pnpm dev:map` | Journey map on :5173 |
| `python -m hermit_keeper api` | Keeper local API only, for UI work |
| `python -m sim all` | Every simulated scenario, time-compressed |
| `python -m sim live` | Three real keepers on three ports, one shared soul |
| `pnpm --filter @hermit/critter dev` | The desktop companion |

## Every laptop has a Hermit

Each laptop runs its own keeper and its own critter, and **every one of them
shows the mascot** — not just whoever is hosting. The holder sees *visiting*;
the others see *waiting*, *sleeping*, or *offline* when their keeper cannot be
reached.

Two ideas stay separate everywhere: the **shared Switch lease** decides who
holds the soul (one answer for the group), and each machine's **own keyboard**
decides whether it is eligible to host (three independent answers). Only the
holder is ever *visiting*.

There is also a small live dashboard anyone can leave open:

```bash
pnpm dev:map
```

then open `http://localhost:<printed-port>/?live=http://127.0.0.1:47801`. The
critter does not need it — it talks to its own keeper directly.

Full setup, failure modes and what is not yet proven:
[`docs/running-on-three-laptops.md`](docs/running-on-three-laptops.md).

**Doing the real three-laptop test?** Follow
[`docs/live-test.md`](docs/live-test.md) — Tailscale, the two integration steps
that still have to happen first, who does what, and the seven runs to make.

## Privacy

Deliberate, and part of the pitch:

- Hermit's brain sees **one folder** you chose (`~/HermitWindow`) — file names
  only, contents never leave your machine and never reach the ledger.
- **Area-level location only** — the centre of your neighbourhood, typed by you
  into your own config. Never your street, never your address. No tracking, and
  the coordinates never leave the group's own Switch server.
- No central server of ours. Only the Switch server the group runs.
- The bedtime rule means Hermit *leaves* when you should sleep. It never rewards
  staying up.
- Overlap finder and quiet-friend nudge are **opt-in**, off by default.

## License

TBD before submission. Switch itself is Apache 2.0 + Commons Clause; we build on
it, we don't resell it.
