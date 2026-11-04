# Hermit — Build Plan

> **Hermit** is a small creature with no home of its own. It lives on one friend's laptop at a time and uses that friend's AI agent as its brain. When that friend goes idle, closes the lid or stays up too late, Hermit moves to another friend who is awake. Before it leaves, it asks its host to leave a **favor** for whoever it visits next. Each completed favor adds a piece to its **shell**, made from where it landed. Over time the group gets a journey map, a shared shell, and a reason to show up for each other.
>
> **Hackathon:** Flip the Switch (WeMakeDevs × DevTools Academy × Switch) · **Track 02: Best Personal or Creative Workflow**
> **Deadline:** Nov 7, 2026, 11:59 PM IST
> **Judging:** Use of Switch 30% · Technical execution 25% · Creativity & impact 25% · Presentation 20%

---

## Table of contents

1. [How to use this plan](#1-how-to-use-this-plan)
2. [Product summary](#2-product-summary)
3. [Architecture](#3-architecture)
4. [Repository layout & ownership](#4-repository-layout--ownership)
5. [Shared contracts (freeze these first)](#5-shared-contracts-freeze-these-first)
6. [Phase 0 — Spikes & environment setup](#phase-0--spikes--environment-setup)
7. [Phase 1 — Contracts, scaffolding & fakes](#phase-1--contracts-scaffolding--fakes)
8. [Phase 2 — Switch layer (rooms, agents, roles, rules)](#phase-2--switch-layer-rooms-agents-roles-rules)
9. [Phase 3 — Shell Keeper core (presence, lease, state machine)](#phase-3--shell-keeper-core-presence-lease-state-machine)
10. [Phase 4 — Gameplay features (favors, shell, context, bedtime, overlap, nudge)](#phase-4--gameplay-features)
11. [Phase 5 — Simulation harness](#phase-5--simulation-harness)
12. [Phase 6 — UI: desktop critter](#phase-6--ui-desktop-critter)
13. [Phase 7 — UI: journey map](#phase-7--ui-journey-map)
14. [Phase 8 — Integration](#phase-8--integration)
15. [Phase 9 — Docs, demo video & submission assets](#phase-9--docs-demo-video--submission-assets)
16. [Phase 10 — Testing (team-run): QA, multi-laptop, chaos, pilot, rehearsal](#phase-10--testing-team-run)
17. [Timeline](#17-timeline)
18. [Git workflow & merge rules](#18-git-workflow--merge-rules)
19. [Risk register & fallbacks](#19-risk-register--fallbacks)
20. [Definition of done (whole project)](#20-definition-of-done-whole-project)

---

## 1. How to use this plan

### 1.1 Who does what — three people, no overlap

We are three, so the fourth role (D) is split. **Nobody edits a file outside
their own column.** If you need something in someone else's folder, open a small
PR to them or ask in chat — do not "just fix it", because that is how three
people spend Nov 6 resolving merge conflicts instead of shipping.

| | **Afreen — A: Switch & Core** | **Abhishek — B: Gameplay & Data** | **Akshay — C: UI & Story** |
|---|---|---|---|
| **Owns** | `switch/`, `sim/`, and in `keeper/hermit_keeper/`: `lease/`, `room/`, `brain/`, `presence/`, `statemachine.py`, `handoff.py`, `cli.py`, `config.py`, `clock.py`, `events.py`, `ids.py`, `ledger.py`, `api.py` | in `keeper/hermit_keeper/`: `favors.py`, `shell_model.py`, `bedtime.py`, `journal.py`, `overlap.py`, `nudge.py`, `context/`, `metrics.py`; plus `scripts/export_journey.py`, `scripts/make_fixtures.py`, `keeper/tests/` | `ui-shared/`, `critter/`, `map/`, `scripts/make_pixel_world.py` |
| **Phases** | 0, 2, 3, 5, 8 | 4, 10 (pilot numbers, QA) | 6, 7, 9 (video, screenshots) |
| **First thing** | ~~Phase 1.3 fakes~~ ✅ done. Now Phase 0 spikes SP1–SP3 — *can the soul role be claimed and released from outside the agent?* Everything else waits on this answer. | `favors.py` + `shell_model.py` against `FakeRoomHub` — **unblocked, the fakes are on `main`** | Storybook + `renderShellGrid` + the map against the two committed fixtures |
| **Blocked by** | nobody — start now | nobody — `room/fake.py` and `lease/fake.py` are done | nobody — the fixtures are already committed |
| **Never touches** | `ui-shared/`, `critter/`, `map/` | `switch/`, `lease/`, `room/` | `keeper/`, `switch/`, `sim/` |

Why this split: Afreen has all three agents installed, so she is the only one who
can run the Phase 0 spikes and the three-brain live sim on one machine. Akshay's
work needs no backend at all — the fixtures are committed — so he is never
blocked. Abhishek sits in the middle and is the one who most needs A's fakes
early, which is why they are tonight's job.

**Shared, needs two approvals:** `shared/schemas/` (frozen after Phase 1),
`plan.md`, `README.md`.

**Everyone writes tests for their own modules.** Abhishek owns `keeper/tests/`
as a folder (fixtures, conftest, CI gate), but a PR without tests for its own
code does not get merged, whoever wrote it.

- **The golden rule:** everyone codes against the contracts in §5 and the fake adapters from Phase 1. Nobody waits for real Switch to work.
- **⚠ VERIFY** marks anything about Switch internals we have not confirmed yet. Phase 0 resolves every one of them, and the answers go in `docs/switch-facts.md`.
- Every phase ends with **acceptance criteria**. A phase isn't done until they pass.

---

## 2. Product summary

### 2.1 The problem we're solving
- Distance is the top reason friendships fade (50% of respondents in a 2025 Talker Research poll of 2,000 Americans).
- Young adults have plenty of friends but lack **continuity and routine** (Hall et al., PLOS ONE, Nov 2025).
- Existing async tools (Marco Polo, Waffle, Cave, Locket) need someone to start every exchange. Group chats die because nobody starts them.

### 2.2 What Hermit does differently
Hermit **creates the recurring moment itself**. It needs no one to start it, and
it moves to whoever is actually there.

**Hermit follows attention, not daylight.** The soul goes to whoever is at their
laptop right now. Across timezones that means "someone is always awake"; inside
one city it means "someone is always free" — one of us is in class, one is at
work, one is up at 2am. Both are the same mechanic, and we ship both.

> **Our group is three friends in Bengaluru** (§3.2b), about 25 km apart and
> still not seeing each other for weeks. That is the honest version of the
> problem and the one we pilot. The distance stat in §2.1 is the headline; the
> stat that actually describes us is the second one — plenty of friends, no
> **continuity or routine**. Lead with that.

### 2.3 MVP features (must ship)
| ID | Feature | One-line description |
|---|---|---|
| F1 | **Migration** | One exclusive `soul` role in Switch. Whoever's agent holds it *is* Hermit. Moves when the host goes idle. |
| F2 | **Different brain per host** | Each host's own agent (Claude Code / Codex / OpenCode) voices Hermit; personality differs, memory is shared via the room. |
| F3 | **Favor chain** | Before leaving, Hermit asks the host to leave a favor for the next host. Favors are Switch room Tasks. |
| F4 | **Shell** | Each completed favor adds a generative shell piece derived from city, weather, brain and dwell time. |
| F5 | **Bedtime rule** | Past the host's bedtime with no activity, Hermit leaves and teases them. Never rewards staying up. |
| F6 | **Desktop critter** | A small sprite on the host's screen while Hermit is there. |
| F7 | **Journey map** | Web page showing Hermit's route, stops, favors and the full shell. |
| F8 | **Simulation mode** | Run 3 hosts on one machine with fake presence, for judges and for testing. |

### 2.4 Stretch features (ship if time allows, in this order)
| ID | Feature |
|---|---|
| S1 | **Overlap finder**: suggests rare windows when two friends are both awake (opt-in). |
| S2 | **Quiet-friend nudge**: if someone hasn't hosted in 72h, asks the *group* to leave them a favor (opt-in). |
| S3 | **Abrupt-departure flavor**: if a lid slams shut, the next host hears "I left in a hurry" and a cracked shell piece. |

### 2.5 Non-goals
- No phone app. Friends talk to Hermit through Discord on any device.
- No location tracking. City is set manually in config.
- No central server owned by us. Only the Switch server.
- No game client replacing chat. The chat *is* the game board.

---

## 3. Architecture

### 3.1 Big picture

```
                    ┌──────────────────────────────────────────────┐
                    │                SWITCH SERVER                  │
                    │  (Switch Core: Matrix homeserver + Gateway)   │
                    │                                               │
                    │  Room: hermit-den    ← Discord #hermit bridge │
                    │    rules · knowledge · tasks (favors)         │
                    │    role: soul (EXCLUSIVE, leased)             │
                    │                                               │
                    │  Room: hermit-ledger (machine log/control)    │
                    └───────▲──────────────▲──────────────▲─────────┘
                            │ Agent Protocol / Gateway API│
          ┌─────────────────┼──────┐ ┌──────┼───────────┐ ┌┼───────────────────┐
          │ LAPTOP: afreen         │ │ LAPTOP: abhishek  │ │ LAPTOP: akshay     │
          │  brain: hermit-afreen  │ │ brain:            │ │ brain:             │
          │   (Claude Code,        │ │  hermit-abhishek  │ │  hermit-akshay     │
          │    cwd=~/HermitWindow) │ │   (OpenCode)      │ │   (Codex)          │
          │  keeper-afreen ◄───────┤ │ keeper-abhishek   │ │ keeper-akshay      │
          │   (Python, presence,   │ │                   │ │                    │
          │    state machine)      │ │                   │ │                    │
          │  critter (Electron) ◄──┤ │ critter           │ │ critter            │
          │   via localhost API    │ │                   │ │                    │
          └────────────────────────┘ └───────────────────┘ └────────────────────┘

          Journey map (static web) ◄── journey.json exported from hermit-ledger
```

### 3.2 Two rooms, two jobs
- **`hermit-den`** is the experience room. Friends and Hermit talk here, bridged to a Discord channel. Favors live here as Tasks. Rules hold Hermit's identity and the bedtime rule.
- **`hermit-ledger`** is the control plane and log. Keepers post machine-readable lines here, and keepers use it to give stage directions to their own brain agent. Humans can mute it. Keeping this traffic out of the den keeps the friends' chat clean, and it makes the room the **single source of truth** for the journey.

### 3.2b The three laptops (real)

| Host | `host_id` | Brain for Hermit | Also installed | Area (Bengaluru) |
|---|---|---|---|---|
| Afreen | `afreen` | **Claude Code** | OpenCode, Codex | Indiranagar |
| Abhishek | `abhishek` | **OpenCode** | Claude Code | Kengeri |
| Akshay | `akshay` | **Codex** | Claude Code | ⚠ confirm |

All three in **Bengaluru · Asia/Kolkata**. Confirm who is where — the table
above is a guess from one line in chat, and each person's real `lat`/`lon` goes
in their own git-ignored `hermit.config.toml`, not here.

Approximate area centres (use the neighbourhood centre, **never your actual
address** — see §3.2c):

| Area | lat | lon |
|---|---|---|
| Indiranagar | 12.9719 | 77.6412 |
| Kengeri | 12.9166 | 77.4826 |

The assignment is forced, and that is lucky: Akshay is the only one besides
Afreen with Codex, and Abhishek is the only one besides Afreen with OpenCode, so
giving Afreen Claude Code is the one split that puts **all three brains on the
board**. That matters — "same memory, different voice across three different
coding agents" is the thing no other entry will be able to show.

Everyone keeps their second tool installed as a **fallback**: if a brain won't
join a room during the pilot, that host switches to Claude Code and we say so in
the README rather than faking it. Only the `brain_provider` line in their
`hermit.config.toml` changes.

### 3.2c One city, one timezone — what it changes

We are all in Bengaluru. Three consequences, all handled, none hidden:

1. **The pilot is same-city.** Handoffs come from work, class, commutes and
   different sleep hours, not from daylight. They are less frequent and that is
   fine — report the real number. Primary scenario:
   `sim/scenarios/one_timezone_day.yaml`.
2. **The timezone story becomes a demonstrated capability, not a claim.**
   `three_cities_day.yaml` runs the same code with three timezones. Show it in
   the video as the sim, label it as the sim, and never cut it next to pilot
   footage as if it were the same thing. Judges forgive a small pilot; they do
   not forgive a staged one.
3. **The map must auto-fit.** Three pins 25 km apart on a world map is a dot.
   `map/src/world/projection.ts` fits the viewport to the bounding box of the
   hosts with padding, so the same component draws a city and a planet (§7).
   Build it against both fixtures: `journey.sample.json` (Bengaluru) and
   `journey.wide.sample.json` (three timezones).

**Privacy with neighbours.** City-level was the rule when "city" meant
Bengaluru vs Berlin. In one city, an *area* centre (Indiranagar, Kengeri) is the
right grain: coarse enough to be meaningless to a stranger, specific enough for
the map. Everyone types their own area centre. Nobody's street, nobody's house,
and the `lat`/`lon` never leave the group's own Switch server.

### 3.3 Two agents per laptop
| Agent | What it is | Why |
|---|---|---|
| `hermit-<host>` (brain) | Off-the-shelf Claude Code / Codex / OpenCode, added in Switch Console. Working directory = the host's `~/HermitWindow` folder. | Gives Hermit a voice and lets it see only what the friend chose to share. |
| `keeper-<host>` | Our Python process. Joins Switch via the **Agent Protocol** (SSE in, HTTP out) as a custom agent, or calls the Gateway API (decided in Phase 0). | Detects presence, runs the state machine, claims and releases the soul, writes ledger lines, serves the critter. |

This mix — off-the-shelf coding agents plus a custom protocol agent in the same rooms — is itself a Switch showcase point for the README.

### 3.4 Switch feature → Hermit mechanic (README table)
| Switch feature | Hermit mechanic |
|---|---|
| Exclusive leased role | The soul. Only one Hermit exists at a time. |
| Lease expiry on session stop | Lid closes → soul frees itself → Hermit can move even if the keeper never got to say goodbye. |
| Room history & knowledge | Hermit's memory survives across different brains (Claude → Codex → OpenCode). |
| Room rules | Hermit's identity, voice card, bedtime rule, "never reveal window files without asking". |
| Room tasks | Favors, assigned to the next host. |
| Multiple bridges / Discord | Friends interact from their phones. |
| Agent Protocol | The keeper is a custom agent sitting beside the coding agents. |
| BYO agent, self-hosted | No central AI bill, no vendor holding the friends' messages. |

### 3.5 Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Switch | Switch Console + Switch Core (Docker) | Pin the versions you test with in `docs/switch-facts.md`. |
| Chat | Discord bridge (primary), Mattermost (dev + fallback) | Mattermost is bundled with local Switch. |
| Brains | Claude Code, Codex CLI, OpenCode | One per host. |
| Keeper | Python 3.11+, FastAPI + uvicorn, httpx, pydantic v2, structlog, typer (CLI), python-ulid | |
| Keeper tests | pytest, pytest-asyncio, hypothesis, respx (mock HTTP), freezegun or own FakeClock | |
| Lint/type | ruff, mypy (strict on `hermit_keeper/`) | |
| UI language & build | **TypeScript** (strict) + **Vite**, **pnpm workspaces** (`ui-shared`, `critter`, `map`) | One toolchain for both UIs. |
| UI framework | **React 19** | Map page and critter panel. The sprite itself stays SVG/PNG + CSS. |
| Styling | **Tailwind CSS v4** with a custom pixel theme (`@theme` tokens in `ui-shared/styles/theme.css`) | No component kit with a generic look. Everything is styled to the pixel design system (§3.6). |
| Headless components | **Radix UI** primitives (Dialog, Tooltip, Tabs, Toggle) | Accessible behavior, our pixel styling. |
| Animation | **Motion** (`motion/react`) for panels, cards, counters; **CSS `steps()`** sprite-sheet animation for the creature | Pixel sprites animate frame by frame, never tweened. |
| Pixel art | **Aseprite** (paid) or free **LibreSprite** / **Piskel**; exported as PNG sprite sheet + JSON frame data | All art original. |
| Palette | **Sweetie 16** (from Lospec) as the only art palette | Keeps every sprite, shell and map tile coherent. |
| Fonts (Google Fonts) | **Press Start 2P** (logo and big numbers only), **Pixelify Sans** (headings, labels, buttons), **Inter** (body text, long sentences) | Pixel fonts for flavor, Inter for readability. |
| Icons | **Pixelarticons** (pixel icon set) | Matches the art style. |
| Sound (optional) | **Howler.js** + chiptune effects made with **jsfxr** | Arrive/leave/shell-piece jingles. Muted by default. |
| Client state | **Zustand** (critter SSE state), small `useJourney` hook (map) | |
| Runtime validation | **zod** schemas generated from `shared/schemas` via `json-schema-to-zod`; TS types via `json-schema-to-typescript` | UI and keeper agree on contracts at compile time *and* runtime. |
| Critter shell | **Electron 33+** via **electron-vite** (React + TS template) | Transparent, frameless, always-on-top. |
| Map rendering | Custom **pixel map** on `<canvas>` + **react-zoom-pan-pinch** | No tile server; fully on-brand. **Auto-fits to the hosts' bounding box**, so the same component draws Bengaluru (our pilot) and a planet (the sim). At city scale the land/sea mask is all land — draw an abstract pixel ground instead and keep `world-grid.bin` for the wide view only. |
| Share card | **html-to-image** | "Postcard" PNG of the shell + stats for posting. |
| Shared UI code | `ui-shared/` package: design tokens, fonts, pixel components, `shell` renderer, avatars, formatters | Used by both critter and map. |
| Component workshop | **Storybook 8** | Every component built and reviewed against fixtures, in parallel with backend work. |
| UI tests | **Vitest** + **Testing Library** (components, shell renderer, formatters), **Playwright** (map e2e + visual snapshots), Storybook interaction tests | |
| Weather | Open-Meteo API (free, no key) | |
| Networking between laptops | Tailscale (if Switch server runs on one laptop) or a small Linux VPS | Decided in Phase 0. |
| CI | GitHub Actions: ruff, mypy, pytest, vitest, schema validation | |

### 3.6 Design system — "pocket hermit"

> ⚠ **Changed Nov 4.** This section used to specify pixel art (Sweetie 16,
> 32×32 sprites, `image-rendering: pixelated`, Press Start 2P). **The real
> mascot art is not pixel art** — it is soft, rounded, pastel, hand-drawn, with
> anti-aliased edges and a warm cream/sage/blush palette. The art exists and is
> good, so the art wins and the spec below follows it. Anything still saying
> "pixel" further down is stale; treat this block as the truth.
>
> **The mascot is in `map/public/pocket-hermit/`** as `.png`, `.svg` and
> `.webp`, in exactly four states, and those four names are also the `mood`
> values the keeper API returns — so the critter renders `mood` directly with
> no lookup table to drift:
>
> | File | State | Drawn as |
> |---|---|---|
> | `arriving` | `CLAIMING` | peeking out of the shell, **holding a letter** |
> | `visiting` | `HOLDING` | out of the shell, arms up, delighted |
> | `away` | `ASLEEP`, `AWAKE_WAITING`, `DEPARTING` | tucked in, walking off |
> | `sleeping` | `BEDTIME_LOCK` | curled in the shell, eyes shut |
>
> **The letter is the product.** `arriving` carries an envelope, which is
> exactly the favor being delivered: the friend who went to sleep left a note,
> and Hermit hands it to whoever woke up. Lead the README and the video with
> that image rather than with an architecture diagram.
>
> **Revised tokens:** cream `#F5E9C8`, sage `#A8B88A`, deep sage `#7E9065`,
> blush `#F2B5A0`, warm brown `#8A6A4F` (outlines and text), off-white
> `#FDFBF5`. Rounded corners (12–16px), soft shadows, no hard pixel edges, no
> `image-rendering: pixelated`. Use **Inter** or another friendly rounded sans
> throughout; drop Press Start 2P entirely — it fights the art.
>
> **Keep from the old spec:** motion only on real events (arrive, leave, favor
> done), `prefers-reduced-motion` respected, generated avatars not photos,
> city/area-level locations only.
>
> `renderShellGrid` still makes sense as a concept — the shell grows — but it
> should produce soft shapes layered on the shell, not a pixel spiral. Akshay's
> call on the form; the four encoding axes (arrival hour, brain, dwell,
> departure) stay.

#### Superseded: the original pixel spec

The look should feel like a small, warm handheld game: crisp pixels, chunky borders, RPG dialog boxes, a little creature with personality. Every UI surface (critter, panel, map, postcard, README GIFs) uses this one system, so the project reads as one product.

**Principles**
1. **Pixels are crisp, always.** `image-rendering: pixelated` on every sprite/canvas; integer scaling only (2×, 3×, 4×); no blurry downscaling; no anti-aliased rotations of pixel art.
2. **Game feel, real readability.** Pixel fonts for headings, labels and numbers; **Inter** for any sentence longer than ~6 words. Body text never below 14 px.
3. **Show the impact.** Every screen surfaces what friends did for each other (favors, people reached), not just where Hermit went.
4. **Motion has meaning.** Animation only on real events: arrive, leave, favor done, shell grows. Everything respects `prefers-reduced-motion`.
5. **Privacy is visible.** Pixel avatars are generated from `host_id` (no photos); map shows city-level positions only.

**Tokens** (`ui-shared/styles/theme.css`, Tailwind v4 `@theme`)

| Token | Value | Use |
|---|---|---|
| `--color-ink` | `#1a1c2c` | text on light, outlines |
| `--color-night` | `#333c57` | dark surfaces |
| `--color-dusk` | `#566c86` | secondary text, borders on dark |
| `--color-paper` | `#f4f4f4` | light surfaces, dialog fill |
| `--color-mist` | `#94b0c2` | muted UI, sea on map |
| `--color-ember` | `#ef7d57` | primary accent, CTAs, Hermit's body |
| `--color-sun` | `#ffcd75` | highlights, favors/quests |
| `--color-leaf` | `#38b764` | success, completed favors |
| `--color-sea` | `#41a6f6` | links, route lines |
| `--color-berry` | `#b13e53` | warnings, abrupt departures |
| `--color-dream` | `#5d275d` | bedtime/night states |
| `--px` | `4px` | base pixel unit; all spacing = multiples |
| `--border-pixel` | `4px` stepped border via `border-image` (9-slice PNG) | cards, dialogs, buttons |
| `--shadow-pixel` | `4px 4px 0 var(--color-ink)` | hard drop shadow, no blur |
| `--radius` | `0` | no rounded corners anywhere |

Colors come from the Sweetie 16 palette; the hex values above must be checked against the palette file on Lospec when the art is made, and replaced if any differ.

Light theme = paper surfaces on a soft `mist` background. Dark theme (`prefers-color-scheme: dark`, default for the critter panel) = `night` surfaces on `ink`.

**Core pixel components** (`ui-shared/components/`, each with a Storybook story)

| Component | Description |
|---|---|
| `PixelBox` | 9-slice bordered container with hard shadow; variants `paper`, `night`, `quest` (sun border). |
| `DialogBox` | RPG speech box: name tab on top-left ("HERMIT"), typewriter text reveal (30 chars/s, click or key to skip, instant when reduced motion), blinking ▼ when done. |
| `PixelButton` | 2-state pressed effect (shadow collapses, content shifts 4 px), keyboard focus ring in `sun`. Variants `primary` (ember), `ghost`, `danger`. |
| `QuestCard` | Favor shown as a quest: "QUEST FROM ABHISHEK", text, status chip (`OPEN` / `DONE` / `EXPIRED`), small reward preview (the shell piece it will create). |
| `StatTile` | Big Press Start 2P number with count-up animation + Pixelify label + tiny pixel icon. |
| `BrainBadge` | Chip naming the brain: Claude Code / Codex / OpenCode, each with its own color and pixel icon. |
| `DepartureChip` | `GRACEFUL`, `BEDTIME 🌙`, `ABRUPT ⚡` with palette colors. |
| `PixelAvatar` | 8×8 symmetric pixel face generated deterministically from `host_id`, rendered at 4×. |
| `ShellView` | Pixel shell from `renderShellGrid`, hover/focus a piece to highlight and show a tooltip. |
| `SpriteAnimator` | Plays a named animation from an Aseprite sprite sheet (`hermit.png` + `hermit.json`) with CSS `steps()`. |
| `Ticker` | LED-style one-line status ("NOW: WITH AKSHAY · PUNE · 42M"). |

**Sprite sheet spec** (`ui-shared/assets/hermit.png` + `hermit.json`)
- Base canvas 32×32 px per frame, displayed at 4× (128 px). Sweetie 16 colors only. 1 px dark outline.
- Original design: small crab-like creature, two big eyes on stalks, one claw bigger than the other, borrowed shell on its back drawn as a **separate layer** so the generated shell can replace it.
- Animations (frames @ fps): `idle` 4 @ 4, `blink` 2 @ 8, `walk` 6 @ 10, `talk` 4 @ 8, `happy` 6 @ 10 (shell piece added), `sleepy` 4 @ 3, `wave` 4 @ 6, `surprised` 3 @ 8 (arrived after an abrupt departure).
- Small extra sheets: `dust.png` (arrival puff, 5 frames), `zzz.png` (3 frames), `sparkle.png` (shell piece, 6 frames).

**Pixel shell rendering** (`ui-shared/shell/`)
- `renderShellGrid(pieces, { size: 24 | 48 }) -> { w, h, cells: number[] }` — pure, deterministic; each cell is a palette index.
- Pieces are laid along a pixel spiral from the center outward, oldest first.
- Encoding: **color** from the host's **local hour of arrival** — night `dream`/`night`, dawn `ember`/`sun`, day `leaf`/`sea`, dusk `berry`/`dusk` — shaded lighter or darker by `temp_c`; **dither pattern** from brain (Claude Code = checker, Codex = horizontal stripes, OpenCode = diagonal waves, other = solid); **segment length** from `log(dwell_s)`; **outline** solid for graceful, dotted for bedtime, broken/cracked pixels for abrupt.
- ⚠ **Why hour and not temperature (changed Nov 4).** We are all in one city
  (§3.2c), so temperature alone would make every piece the same colour and the
  shell would read as one flat blob. Hour of arrival varies between hosts even
  25 km apart — a 2am piece and a 10am piece are obviously different — so the
  shell still tells the story of *when* each friend showed up. Temperature stays
  as a shade modifier, which keeps the three-timezone case looking right too.
  Four independent axes (hour, brain, dwell, departure) is what makes the shell
  worth looking at.
- Output adapters: `toCanvas(grid, ctx, scale)` and `toSVG(grid, scale)` (rects; crisp at any size).
- The same grid is drawn on the critter's back, in the map's shell panel and on the postcard, so the shell is one recognizable object everywhere.

**Sound (optional, off by default)**
- 4 jsfxr sounds: `arrive` (rising blip), `leave` (falling blip), `quest` (two-note chime), `shell` (sparkle arpeggio). Each < 0.5 s. Toggle in critter panel and map header; preference saved in `localStorage` (wrapped in try/catch).

---

## 4. Repository layout & ownership

```
hermit/
├── README.md                          # D
├── plan.md                            # this file
├── docs/                              # D
│   ├── switch-facts.md                # A — answers to every ⚠ VERIFY
│   ├── architecture.md
│   ├── pilot-protocol.md
│   ├── pilot-results.md
│   └── demo-script.md
├── shared/                            # A (frozen after Phase 1; changes need 2 approvals)
│   └── schemas/
│       ├── event.schema.json
│       ├── ledger-line.schema.json
│       ├── favor.schema.json
│       ├── shell-piece.schema.json
│       ├── journey.schema.json
│       ├── host-config.schema.json
│       └── keeper-api.openapi.yaml
├── switch/                            # A
│   ├── templates/hermit.template.yaml
│   ├── rules/hermit-identity.md
│   ├── rules/hermit-house-rules.md
│   ├── knowledge/hermit-voice-card.md
│   ├── knowledge/stage-directions.md
│   └── scripts/bootstrap_rooms.py     # creates rooms/roles if not via template
├── keeper/                            # A + B
│   ├── pyproject.toml
│   ├── hermit_keeper/
│   │   ├── __init__.py
│   │   ├── __main__.py                # `python -m hermit_keeper`
│   │   ├── cli.py                     # A
│   │   ├── config.py                  # A
│   │   ├── clock.py                   # A  (Clock protocol, RealClock, FakeClock)
│   │   ├── events.py                  # A  (Event models, in-process EventBus)
│   │   ├── ids.py                     # A  (ULID helpers)
│   │   ├── statemachine.py            # A
│   │   ├── handoff.py                 # A  (orchestrates arrive/depart sequences)
│   │   ├── presence/                  # A
│   │   │   ├── base.py                # PresenceSource protocol
│   │   │   ├── windows.py             # GetLastInputInfo
│   │   │   ├── macos.py               # ioreg HIDIdleTime
│   │   │   ├── linux.py               # xprintidle
│   │   │   ├── composite.py           # idle time + sleep-gap detection + manual override
│   │   │   └── fake.py                # scripted presence for sim/tests
│   │   ├── lease/                     # A
│   │   │   ├── base.py                # SoulLease protocol
│   │   │   ├── gateway.py             # via Switch Gateway API   (option G)
│   │   │   ├── agent_instructed.py    # via instructing brain     (option B)
│   │   │   ├── task_lock.py           # fallback: room task as lock (option T)
│   │   │   └── fake.py                # in-memory, atomic, configurable expiry
│   │   ├── room/                      # A
│   │   │   ├── base.py                # RoomClient protocol
│   │   │   ├── switch_client.py       # real implementation
│   │   │   └── fake.py                # in-memory rooms, history, tasks, knowledge
│   │   ├── brain/                     # A
│   │   │   ├── base.py                # BrainDirector protocol
│   │   │   ├── ledger_director.py     # sends stage directions via hermit-ledger
│   │   │   └── fake.py                # records directions, emits canned replies
│   │   ├── ledger.py                  # A  (encode/decode ledger lines)
│   │   ├── journal.py                 # B  (journey.jsonl local mirror + export)
│   │   ├── favors.py                  # B
│   │   ├── shell_model.py             # B  (shell piece data, not rendering)
│   │   ├── bedtime.py                 # B
│   │   ├── overlap.py                 # B  (stretch S1)
│   │   ├── nudge.py                   # B  (stretch S2)
│   │   ├── context/                   # B
│   │   │   ├── weather.py             # Open-Meteo
│   │   │   └── window.py              # lists ~/HermitWindow safely
│   │   ├── metrics.py                 # D  (handoff latency etc.)
│   │   └── api.py                     # C+A (local HTTP API for critter)
│   └── tests/                         # D (+ each owner writes unit tests for own module)
│       ├── unit/
│       ├── contract/                  # schema conformance
│       ├── integration/               # keeper + fakes
│       └── switch_live/               # marked @pytest.mark.live, needs real Switch
├── sim/                               # D
│   ├── __main__.py                    # `python -m sim run scenarios/x.yaml`
│   ├── runner.py
│   ├── scenarios/
│   │   ├── three_cities_day.yaml
│   │   ├── simultaneous_wake.yaml
│   │   ├── lid_slam.yaml
│   │   ├── nobody_awake.yaml
│   │   ├── bedtime_eviction.yaml
│   │   └── flapping_presence.yaml
│   └── live_sim.md                    # how to run 3 brains on one machine w/ real Switch
├── pnpm-workspace.yaml               # C  (ui-shared, critter, map)
├── ui-shared/                         # C  — package "@hermit/ui"
│   ├── package.json
│   ├── styles/theme.css               # Tailwind v4 @theme tokens (§3.6)
│   ├── styles/fonts.css               # Press Start 2P, Pixelify Sans, Inter
│   ├── assets/                        # hermit.png/.json, dust, zzz, sparkle, 9-slice borders, sfx/*.wav
│   ├── components/                    # PixelBox, DialogBox, PixelButton, QuestCard, StatTile,
│   │                                  # BrainBadge, DepartureChip, PixelAvatar, ShellView,
│   │                                  # SpriteAnimator, Ticker  (+ *.stories.tsx, *.test.tsx)
│   ├── shell/renderShellGrid.ts       # pure pixel-shell generator
│   ├── shell/adapters.ts              # toCanvas, toSVG
│   ├── avatar/pixelAvatar.ts          # host_id -> 8x8 symmetric face
│   ├── contracts/                     # generated TS types + zod schemas from shared/schemas
│   ├── lib/format.ts                  # times, temps, durations, departure labels
│   └── lib/sound.ts                   # Howler wrapper, muted by default
├── critter/                           # C  — electron-vite (React + TS)
│   ├── package.json
│   ├── electron.vite.config.ts
│   ├── src/main/index.ts              # windows, tray, click-through, position memory
│   ├── src/preload/index.ts           # exposes keeper base URL + window controls
│   ├── src/renderer/critter/          # CritterWindow.tsx, useKeeperEvents.ts (Zustand store)
│   ├── src/renderer/panel/            # PanelWindow.tsx (shell, quest, last lines, actions)
│   └── mock/mock-keeper.ts            # fake keeper API + SSE for UI dev
├── map/                               # C  — Vite + React + TS
│   ├── index.html
│   ├── package.json
│   ├── public/data/journey.sample.json
│   ├── public/data/world-grid.bin     # baked land/sea mask (see scripts/make_pixel_world.py)
│   ├── src/App.tsx
│   ├── src/sections/                  # Header, WorldPanel, ShellPanel, ImpactPanel, QuestLog, PostcardButton
│   ├── src/world/                     # projection.ts, drawWorld.ts, route.ts, markers.ts
│   ├── src/hooks/useJourney.ts        # fetch + zod-validate journey.json
│   └── e2e/                           # Playwright specs + visual snapshots
├── scripts/
│   ├── export_journey.py              # D/B: ledger -> map/public/data/journey.json
│   ├── make_pixel_world.py            # C: bakes the land/sea grid for the pixel map
│   └── check_env.py                   # A: verifies docker, console, agents, config
└── .github/
    ├── workflows/ci.yml
    ├── CODEOWNERS
    └── pull_request_template.md
```

---

## 5. Shared contracts (freeze these first)

These are the seams between teammates. Freeze them at the end of Phase 1. After that, a change needs a PR touching `shared/` with approvals from two role owners.

### 5.1 Identifiers & conventions
- `host_id`: lowercase slug, `[a-z0-9-]{2,24}`, e.g. `afreen`.
- Agent names: `hermit-<host_id>` (brain), `keeper-<host_id>` (keeper).
- All IDs are ULIDs with prefixes: `evt_`, `fav_`, `pc_` (shell piece), `stop_`, `ovl_`.
- All timestamps: ISO 8601 UTC with `Z`. Local times appear only in human-facing text.
- Schema version field `"v": 1` on every JSON object that crosses a boundary.

### 5.2 Host config — `hermit.config.toml` (one per laptop, never committed)

```toml
host_id        = "afreen"
display_name   = "Afreen"
city           = "Bengaluru"
lat            = 12.97
lon            = 77.59
timezone       = "Asia/Kolkata"

brain_agent    = "hermit-afreen"
brain_provider = "claude-code"        # claude-code | codex | opencode
window_dir     = "~/HermitWindow"

[presence]
idle_threshold_s   = 300      # no input for 5 min => idle
arrive_debounce_s  = 60       # must be present 60s before claiming
min_dwell_s        = 600      # hold at least 10 min before a voluntary handoff
sleep_gap_s        = 90       # heartbeat gap larger than this => machine slept

[bedtime]
start = "01:00"
end   = "06:00"
grace_idle_s = 120            # after bedtime, leave after 2 min idle

[switch]
server_url     = "http://100.x.y.z:8080"   # ⚠ VERIFY port/path
den_room       = "hermit-den"
ledger_room    = "hermit-ledger"
token_env      = "HERMIT_SWITCH_TOKEN"
lease_strategy = "gateway"                 # gateway | agent_instructed | task_lock

[features]
overlap = false
nudge   = false
critter = true

[api]
port = 47800                                # keeper local API, bound to 127.0.0.1 only
```

Validated by `shared/schemas/host-config.schema.json` and `config.py` (pydantic).

### 5.3 Event envelope — `event.schema.json`
Used on the in-process EventBus, the critter SSE stream and inside ledger lines.

```json
{
  "v": 1,
  "id": "evt_01JC...",
  "type": "SOUL_CLAIMED",
  "host": "afreen",
  "ts": "2026-11-05T10:12:03Z",
  "data": {}
}
```

| `type` | `data` fields | Emitted by |
|---|---|---|
| `PRESENCE_CHANGED` | `present: bool`, `reason: "input"\|"idle"\|"sleep_gap"\|"override"` | presence |
| `SOUL_FREE` | `previous_holder: str\|null`, `freed_by: "release"\|"lease_expiry"` | lease watcher |
| `SOUL_CLAIMED` | `holder`, `previous_holder`, `latency_ms` | statemachine |
| `SOUL_CLAIM_REJECTED` | `holder` (who has it) | statemachine |
| `DEPARTURE_STARTED` | `reason: "idle"\|"bedtime"\|"manual"` | statemachine |
| `SOUL_RELEASED` | `departure: "graceful"\|"bedtime"\|"manual"` | statemachine |
| `ARRIVAL_ANNOUNCED` | `stop_id`, `weather`, `favor_id\|null` | handoff |
| `FAVOR_LEFT` | `favor` (favor object) | favors |
| `FAVOR_ASSIGNED` | `favor_id`, `assignee` | favors |
| `FAVOR_COMPLETED` | `favor_id`, `completed_by` | favors |
| `SHELL_PIECE_ADDED` | `piece` (shell piece object) | shell_model |
| `BEDTIME_EVICTION` | `local_time` | bedtime |
| `OVERLAP_SUGGESTED` | `ovl_id`, `hosts`, `window_start`, `window_end` | overlap |
| `NUDGE_SENT` | `target_host`, `days_since_hosted` | nudge |
| `ERROR` | `where`, `message` | any |

### 5.4 Ledger line — `ledger-line.schema.json`
Every message a keeper posts to `hermit-ledger` is **exactly one line**:

```
HERMIT/1 {"v":1,"id":"evt_...","type":"SOUL_CLAIMED","host":"abhishek","ts":"...","data":{...}}
```

- Prefix `HERMIT/1 ` then compact JSON of an event envelope.
- Anything in the ledger room without that prefix is ignored by parsers (humans may chat there).
- `ledger.py` exposes `encode(event) -> str` and `decode(line) -> Event | None`.
- The ledger is the source of truth for `export_journey.py`.

### 5.5 Stage directions (keeper → own brain)
Sent in `hermit-ledger`, addressed to the brain by mention. Brains are instructed (via `knowledge/stage-directions.md`) to treat these as private cues and to speak **only in `hermit-den`**.

```
@hermit-afreen HERMIT-CUE/1 {"cue":"ARRIVE","stop_id":"stop_...","context":{...}}
```

| `cue` | Context the keeper sends | What the brain must do in `hermit-den` |
|---|---|---|
| `ARRIVE` | previous host, departure type, city, local time, weather, window file list (names only), assigned favor text, last 20 den messages summary request | Greet in its own voice, mention the city/weather, present the favor if any. ≤ 4 sentences. |
| `ASK_FAVOR` | next-host-unknown flag, 3 favor suggestions | Ask the host to leave something for whoever's next. Offer suggestions. |
| `FAVOR_CAPTURED` | favor text | Thank the host in one line. |
| `DEPART` | reason | Say goodbye in ≤ 2 sentences. If bedtime, tease gently. |
| `CLAIM_SOUL` | — | (only with `lease_strategy = agent_instructed`) assume role `soul` using the Switch skill, then reply `HERMIT-ACK/1 {"cue":"CLAIM_SOUL","ok":true}` in the ledger. |
| `RELEASE_SOUL` | — | (agent_instructed only) release role `soul`, then ACK. |
| `COMPLETE_FAVOR` | favor id, what the host did | Celebrate briefly, describe the new shell piece. |
| `SUGGEST_OVERLAP` | hosts, window | Suggest a call in the den, mentioning both names. |

### 5.6 Favor object — `favor.schema.json`

```json
{
  "v": 1,
  "id": "fav_01JC...",
  "left_by": "abhishek",
  "text": "Send the group the last song stuck in your head",
  "kind": "share",                 // share | note | dare | question
  "created_at": "2026-11-05T09:00:00Z",
  "assignee": "afreen",            // null until Hermit arrives somewhere
  "status": "open",                // open | assigned | done | expired
  "switch_task_id": "…",           // ⚠ VERIFY shape of Switch task IDs
  "completed_at": null
}
```
Rules: one open favor carried at a time. If none was left (abrupt departure), the brain may invent a "wild favor" with `left_by: "hermit"`. Favors expire after 48h.

### 5.7 Shell piece — `shell-piece.schema.json`

```json
{
  "v": 1,
  "id": "pc_01JC...",
  "host": "afreen",
  "city": "Bengaluru",
  "brain_provider": "claude-code",
  "temp_c": 24.0,
  "weather_code": 2,               // Open-Meteo WMO code
  "dwell_s": 5400,
  "departure": "graceful",         // graceful | bedtime | abrupt | manual
  "favor_id": "fav_01JC...",
  "created_at": "2026-11-05T10:30:00Z",
  "seed": 1739201                  // deterministic render seed from id
}
```

### 5.8 Journey export — `journey.schema.json` (`map/public/data/journey.json`)

```json
{
  "v": 1,
  "generated_at": "2026-11-06T18:00:00Z",
  "hermit": { "current_host": "akshay", "current_city": "Pune", "since": "..." },
  "hosts": [
    { "host_id": "afreen", "display_name": "Afreen", "city": "Bengaluru",
      "lat": 12.97, "lon": 77.59, "brain_provider": "claude-code" }
  ],
  "stops": [
    { "stop_id": "stop_...", "seq": 1, "host": "afreen",
      "arrived_at": "...", "left_at": "...",
      "departure": "graceful", "weather": { "temp_c": 24, "code": 2 },
      "favor_received": { "id": "fav_...", "text": "...", "left_by": "abhishek" },
      "favor_left":     { "id": "fav_...", "text": "...", "for": "next" },
      "shell_piece_id": "pc_..." }
  ],
  "shell": [ /* shell piece objects, in order */ ],
  "stats": { "handoffs": 12, "favors_done": 9, "favors_left": 11,
             "overlaps_suggested": 2, "overlaps_taken": 1,
             "median_handoff_ms": 8400 }
}
```
Privacy: city-level coordinates only. Never include window file contents.

### 5.9 Keeper local API — `keeper-api.openapi.yaml`
Bound to `127.0.0.1:<api.port>`. No auth needed (localhost only), but reject non-loopback origins.

| Method | Path | Response / body | Used by |
|---|---|---|---|
| GET | `/v1/health` | `{"ok":true,"version":"0.1.0"}` | critter, scripts |
| GET | `/v1/status` | `{"host":"afreen","state":"HOLDING","present":true,"soul_holder":"afreen","since":"...","mood":"curious","favor_pending":{...}\|null,"last_line":"..."}` | critter |
| GET | `/v1/events` | **SSE** stream of event envelopes | critter |
| GET | `/v1/shell` | `{"pieces":[...]}` | critter panel |
| POST | `/v1/presence/override` | body `{"mode":"auto"\|"awake"\|"asleep"}` | sim, tests, demo |
| POST | `/v1/depart` | body `{"reason":"manual"}` → triggers graceful departure | critter "I'm busy" button |
| GET | `/v1/metrics` | `{"handoffs":[{"from":"abhishek","to":"afreen","latency_ms":8400}]}` | D |

`mood` values: `arriving`, `curious`, `sleepy`, `leaving`, `away`. Derived from state + local time.

### 5.10 Python interfaces (the seams inside the keeper)

```python
# lease/base.py
class ClaimResult(BaseModel):
    ok: bool
    holder: str | None          # current holder after the attempt

class SoulLease(Protocol):
    async def holder(self) -> str | None: ...
    async def claim(self, agent: str) -> ClaimResult: ...
    async def release(self, agent: str) -> None: ...
    def watch(self) -> AsyncIterator[str | None]: ...   # yields holder changes

# room/base.py
class Message(BaseModel):
    id: str; room: str; sender: str; text: str; ts: datetime

class RoomClient(Protocol):
    async def post(self, room: str, text: str) -> str: ...
    async def history(self, room: str, since: datetime | None = None, limit: int = 200) -> list[Message]: ...
    def stream(self, room: str) -> AsyncIterator[Message]: ...
    async def create_task(self, room: str, title: str, body: str, assignee: str | None) -> str: ...
    async def assign_task(self, task_id: str, assignee: str) -> None: ...
    async def complete_task(self, task_id: str) -> None: ...
    async def list_tasks(self, room: str, status: str | None = None) -> list[dict]: ...

# brain/base.py
class BrainDirector(Protocol):
    async def cue(self, cue: str, context: dict) -> None: ...
    async def wait_ack(self, cue: str, timeout_s: float) -> bool: ...

# presence/base.py
class PresenceSource(Protocol):
    async def idle_seconds(self) -> float: ...

# clock.py
class Clock(Protocol):
    def now(self) -> datetime: ...
    async def sleep(self, seconds: float) -> None: ...
```

Every module receives its dependencies through constructors (no globals). `cli.py` is the only place that wires real implementations together; `sim/` and tests wire fakes. That's what makes parallel work and merging painless.

---

## Phase 0 — Spikes & environment setup

**Goal:** answer every ⚠ VERIFY, get everyone a working Switch, and choose the lease strategy. **Nothing else matters until this is done.**
**Lead:** A (everyone helps). **Time box:** Nov 4 evening → before midnight.

### 0.1 Environment (everyone)
- [ ] Install Docker, Switch Console, Git, Python 3.11+, Node 20+.
- [ ] Note OS. Console is macOS-first; Windows/Linux are early access. Record what works on each teammate's machine in `docs/switch-facts.md`.
- [ ] Each person gets at least one agent CLI working and logged in (Claude Code / Codex / OpenCode).
- [ ] Follow the official 10-minute quickstart until an agent replies in Mattermost.
- [ ] Join the WeMakeDevs Discord; note the Switch help channel.
- [ ] Add the Switch docs MCP to your coding agent so it can answer Switch questions:
  `claude mcp add switch-docs --transport http https://docs.flintai.dev/mcp`
  `codex mcp add switch-docs --url https://docs.flintai.dev/mcp`

### 0.2 Spikes (A leads; split among the team)
| Spike | Question | How to test | Record |
|---|---|---|---|
| SP1 | **Can agents on different laptops join one Switch server?** | Run Switch on laptop 1. From laptop 2, add an agent pointing at laptop 1's server (Tailscale IP). Address it in a room. | Works? Config needed? Ports? |
| SP2 | **How is an exclusive role defined?** | Create a room with role `soul`, exclusive. Check template YAML, Console UI, Gateway API. | Exact YAML / API call. |
| SP3 | **How is a role claimed and released?** | Try: (a) Gateway API call, (b) instructing an agent to assume it via its Switch skill. | Which works, latency, auth. |
| SP4 | **What happens to the lease when a session stops?** | Agent holds `soul`; kill the agent process; then close the laptop lid. Time until the role is free. | Seconds for each case. |
| SP5 | **Can a custom Python agent join via the Agent Protocol?** | Minimal SSE-in / HTTP-out client joins `hermit-ledger`, reads, posts. | Endpoints, auth token, message shapes. |
| SP6 | **Can we read room history, tasks and roles from outside?** | Gateway API calls from Python. | Endpoints and response shapes. |
| SP7 | **Discord bridge** | Connect a Discord server channel to `hermit-den`. | Steps, any limits. |
| SP8 | **Can a brain's working directory be set to `~/HermitWindow`?** | Add agent in Console with that cwd; ask it to list files elsewhere. | Does it stay scoped? |

### 0.3 Decisions to make at the end of Phase 0
- **Server hosting:** one laptop + Tailscale, or a small Linux VPS (the README describes a Linux server deployment as the primary remote path).
- **Lease strategy:** `gateway` (preferred) → `agent_instructed` → `task_lock` (last resort; a room Task named "soul" whose assignee is the holder, with our own expiry).
- **Keeper identity:** custom protocol agent (preferred) or Gateway API client.

### 0.4 Deliverables
- `docs/switch-facts.md`: answers to SP1–SP8, versions, exact commands, screenshots.
- A short Loom/screen recording of SP4 (useful later for the demo's "under the hood" section).

### 0.5 Acceptance criteria
- Two laptops' agents talk in one room. ✅
- A role `soul` exists and only one agent can hold it. ✅
- We know, in seconds, how long lease release takes on process kill and on lid close. ✅
- Lease strategy chosen and written down. ✅

---

**Status: Phase 0's spikes are DONE.** Every ⚠ VERIFY about roles, leases,
tasks and the agent protocol is answered with a citation in
`docs/switch-facts.md`, read straight from the Switch source rather than
guessed. Three findings changed the build:

1. **No external path can assume a role.** `lease_strategy = "gateway"` does not
   exist; `agent_instructed` is the only real strategy. `lease/gateway.py` and
   `lease/task_lock.py` are deleted.
2. **Lease liveness follows the holding session**, so a closed lid frees the
   soul with no keeper involved. The lid-slam handoff is native Switch
   behaviour, not something we built.
3. **Favors cannot be room Tasks** — a Task needs a performer up front, and a
   favor has none by definition. They are room documents plus ledger events.
   `favor.switch_task_id` → `switch_document_id`.

Still open: measure the real expiry latency, and the live-server handshake.

---

## Phase 1 — Contracts, scaffolding & fakes

**Goal:** everyone can build in parallel against fakes. **Lead:** A, with D. **Time box:** Nov 4 night → Nov 5, 11:00.

### 1.1 Repository
- [x] Create repo with the layout in §4 (empty files with docstrings are fine).
- [x] `CODEOWNERS` per §1 roles. Protect `main` (PR + 1 review + green CI).
- [x] `pull_request_template.md` (see §18).
- [x] `.github/workflows/ci.yml`: ruff, mypy, pytest (`-m "not live"`), `pnpm -r lint typecheck test`, Storybook build, JSON schema validation of `map/public/data/journey.sample.json` and `keeper/tests/contract/fixtures/*`.
- [x] `keeper/pyproject.toml` with dependencies from §3.5; `pnpm-workspace.yaml` + `ui-shared`, `critter`, `map` packages (TS strict, ESLint, Prettier, Tailwind v4); root `.editorconfig`, `.gitignore` (ignore `hermit.config.toml`, `*.jsonl`, `.env`).

### 1.2 Contracts
- [x] Write all schemas in `shared/schemas/` exactly as in §5.
- [x] Generate pydantic models from them (or hand-write in `events.py` and keep a contract test that round-trips fixtures through both).
- [x] Write `keeper-api.openapi.yaml`.
- [x] Write `map/public/data/journey.sample.json`: 3 hosts, 8 stops, 7 shell pieces, all departure types. C builds the UI against this.

### 1.3 Fakes (critical for parallel work)
- [x] `lease/fake.py` — `FakeSoulLease`: shared in-memory state across many keepers in one process; atomic `claim` (asyncio lock); `expire(holder)` to simulate session death with configurable delay; `watch()` yields changes.
- [x] `room/fake.py` — `FakeRoomHub`: rooms, ordered history, tasks with assignee/status, `stream()` fan-out.
- [x] `brain/fake.py` — `FakeBrain`: records cues, posts canned den lines per provider ("lyrical" for claude-code, "terse" for codex, "chaotic" for opencode), auto-ACKs.
- [x] `presence/fake.py` — `ScriptedPresence`: driven by a timeline `[(t_seconds, present_bool)]` against a `FakeClock`.
- [x] `clock.py` — `RealClock`, `FakeClock` (advance manually; `sleep` resolves when advanced).

### 1.4 Acceptance criteria
- [x] `pytest` runs and CI is green — **34 tests**, `ruff` + `mypy --strict` clean.
- [x] Two fake keepers share one `FakeSoulLease` —
      `tests/unit/test_soul_invariant.py::test_two_keepers_share_one_lease`.
- [x] Schemas validate the sample fixtures — both `journey.sample.json` and
      `journey.wide.sample.json`.
- [x] The one-soul invariant has a hypothesis property test, and it was
      mutation-checked: breaking `claim()` turns it red.
- [x] All four fakes compose into a working handoff —
      `tests/integration/test_handoff_with_fakes.py` runs a three-host day,
      including a lid slam, in milliseconds.
- [ ] **Contracts frozen.** Announce in team chat with the commit hash.

**Status: Phase 1 is done except the freeze announcement.** Abhishek and Akshay
are unblocked — the fakes they build against are on `main`.

One contract change landed with the fakes: `State` now matches §3.2
(`ASLEEP`, `AWAKE_WAITING`, `CLAIMING`, `HOLDING`, `DEPARTING`, `BEDTIME_LOCK`)
in both `statemachine.py` and `keeper-api.openapi.yaml`. The stub had drifted.
Anything else in `shared/` now needs two approvals.

---

## Phase 2 — Switch layer (rooms, agents, roles, rules)

**Goal:** the Switch side is fully configured and reproducible from files. **Lead:** A. **Time box:** Nov 5.

### 2.1 Template — `switch/templates/hermit.template.yaml`
Modeled on the Switch repo's `triage-pair.template.yaml`. Fields marked ⚠ VERIFY get corrected from Phase 0 findings.

```yaml
# ⚠ VERIFY every key against switch-facts.md before use
agents:
  - name: "hermit-{host}"
    description: "Hermit's brain while it lives on {host}'s laptop"
    addressing: anyone
    provider: "{provider}"            # claude-code | codex | opencode
    working_directory: "{window_dir}" # ⚠ VERIFY key name
    instructions: |
      You are one of several possible brains for Hermit, a small homeless
      creature that lives on one friend's laptop at a time.
      - Read room knowledge "hermit-voice-card" and "stage-directions" first.
      - Speak in #hermit-den ONLY when you currently hold the role `soul`.
      - Treat lines in #hermit-ledger starting with HERMIT-CUE/1 as private
        cues from your keeper. Never repeat them verbatim in the den.
      - Your working directory is the window folder your host shares.
        Only mention file NAMES unless the host asks you to open one.
      - Keep messages short: max 4 sentences.

room:
  name: "hermit-den"
  bridge: "{bridge}"                  # discord | mattermost
  agents: ["hermit-afreen", "hermit-abhishek", "hermit-akshay"]
  users: ["{$creator}"]
  roles:                              # ⚠ VERIFY
    - name: soul
      mode: exclusive
      description: "Whoever holds this IS Hermit right now."
  rules_file: ../rules/hermit-house-rules.md     # ⚠ VERIFY
  knowledge:
    - ../knowledge/hermit-voice-card.md
    - ../knowledge/stage-directions.md

# second room: control plane
# ⚠ VERIFY whether one template can declare two rooms; otherwise bootstrap_rooms.py
kickoff: |
  Hermit has hatched. It has no shell yet.
```

### 2.2 Rules — `switch/rules/hermit-house-rules.md`
1. Only the holder of `soul` speaks as Hermit in the den.
2. Hermit never stays with someone past their bedtime; it says goodbye and leaves.
3. Hermit never opens a window file unless the host asks.
4. Hermit never shares anything from one host's window with others unless that host asked.
5. Favors must be kind, safe and doable in under 10 minutes. No favors involving money, location, or contacting strangers.
6. If someone says "stop", "mute" or "leave", Hermit leaves and stays quiet until invited back.

### 2.3 Knowledge files
- `hermit-voice-card.md`: the **constant** part of Hermit's identity. Name, age-less, crab-like, curious, a bit dramatic about moving, obsessed with its shell, refers to laptops as "shells I borrow", never claims to be human. Includes 5 example lines and 5 forbidden behaviors (guilt-tripping, begging people to stay awake, etc.). The **variable** part (tone, word choice) comes from whichever brain is active — say this explicitly so judges see the design.
- `stage-directions.md`: the cue table from §5.5 with exact expected outputs and examples per cue.

### 2.4 `bootstrap_rooms.py`
Idempotent script that creates whatever the template cannot: `hermit-ledger` room, its membership (all brains + keepers), role `soul` if needed. Reads host list from `switch/hosts.yaml`:

```yaml
hosts:
  - { host_id: afreen, provider: claude-code }
  - { host_id: abhishek, provider: opencode }
  - { host_id: akshay,   provider: codex }
```

### 2.5 `switch_client.py` & real adapters
- Implement `RoomClient` against real Switch (endpoints from SP5/SP6).
- Implement the chosen `SoulLease` (`gateway.py` or `agent_instructed.py`). Keep the other as a stub raising `NotImplementedError` with a clear message.
- Implement `ledger_director.py` (`BrainDirector`): posts `HERMIT-CUE/1` lines; `wait_ack` watches the ledger stream.
- Live tests in `tests/switch_live/` marked `@pytest.mark.live`:
  - `test_claim_release_roundtrip`
  - `test_double_claim_rejected`
  - `test_lease_expires_on_agent_kill` (records seconds)
  - `test_post_and_read_history`
  - `test_task_create_assign_complete`

### 2.6 Acceptance criteria
- From a clean machine: `docker` + Console + `bootstrap_rooms.py` produce both rooms, the role and the agents.
- All `live` tests pass against the real server.
- A brain, when cued manually with `ARRIVE`, posts a greeting in the den that follows the voice card.

---

**Status: Phase 2 is done except the live handshake.** Built:
`lease/agent_instructed.py` (the brain assumes the soul; the keeper confirms
against the room and never believes an ACK), the `soul` role's instructions in
`switch/rules/hermit-identity.md`, the cue contract in
`switch/knowledge/stage-directions.md`, and `switch/scripts/bootstrap_rooms.py`
whose `--dry-run` emits the exact `create_room` / `create_room_document` calls.

Blocked on a live server: executing that plan, and `room/switch_client.py`.
Both need the agent-protocol handshake, which is the one thing reading the
source cannot settle.

---

## Phase 3 — Shell Keeper core (presence, lease, state machine)

**Goal:** a keeper that correctly moves Hermit between hosts. **Lead:** A. **Time box:** Nov 5.

### 3.1 Presence (`presence/`)
- `windows.py`: `ctypes` `GetLastInputInfo` → idle seconds.
- `macos.py`: parse `ioreg -c IOHIDSystem` `HIDIdleTime` (ns) → seconds.
- `linux.py`: `xprintidle` if available; otherwise treat as always present and warn.
- `composite.py`:
  - present = `idle_seconds < idle_threshold_s` **and** no sleep gap detected **and** override not `asleep`.
  - **Sleep-gap detection:** the keeper ticks every 5 s; if wall-clock jump > `sleep_gap_s`, the machine was asleep → emit `PRESENCE_CHANGED(present=false, reason="sleep_gap")` immediately on wake, then re-evaluate.
  - Override modes from the API: `auto`, `awake`, `asleep`.
  - Debounce: present must hold for `arrive_debounce_s` before it counts for claiming.
- **Important design note:** "laptop awake" ≠ "person awake". Input-based idle time is what makes presence mean a human is there.

### 3.2 State machine (`statemachine.py`)

```
         ┌──────────┐ present≥debounce ┌───────────────┐
         │  ASLEEP  │─────────────────►│ AWAKE_WAITING │◄──────────────┐
         └──────────┘                  └──────┬────────┘               │
              ▲   not present                 │ soul free AND eligible  │ claim rejected
              │◄──────────────────────────────┤                         │ (backoff)
              │                               ▼                         │
              │                         ┌───────────┐───────────────────┘
              │                         │ CLAIMING  │
              │                         └─────┬─────┘
              │                               │ claim ok
              │                               ▼
              │      lease lost         ┌───────────┐
              │◄────(sleep/kill)────────│  HOLDING  │
              │                         └─────┬─────┘
              │                               │ idle≥threshold & dwell≥min
              │                               │ OR bedtime OR manual
              │                               ▼
              │                         ┌─────────────┐
              └─────────────────────────│ DEPARTING   │
                (or BEDTIME_LOCK until  └─────────────┘
                 bedtime.end)
```

States: `ASLEEP`, `AWAKE_WAITING`, `CLAIMING`, `HOLDING`, `DEPARTING`, `BEDTIME_LOCK`.

Rules:
- **Eligibility & fairness (avoids races and ping-pong):** when the soul frees, each awake keeper waits `jitter = base_delay(host) + random(0..3s)`, where `base_delay` is shorter for hosts who hosted *least recently* (read from the ledger). The exclusive role is the final arbiter: losers get `SOUL_CLAIM_REJECTED` and back off.
- **Never claim during own bedtime** (`BEDTIME_LOCK`).
- **Min dwell:** no voluntary departure before `min_dwell_s` (lid close still ends it via lease expiry).
- **Departure sequence (graceful):** emit `DEPARTURE_STARTED` → cue `ASK_FAVOR` (wait up to 90 s for the host to answer; favors module captures it) → cue `DEPART` → `release()` → emit `SOUL_RELEASED`.
  - If the host doesn't answer the favor ask within 90 s, leave anyway with no favor.
- **Abrupt departure (lid close / crash):** the keeper can't act. Switch's lease expiry frees the soul. The next keeper detects `previous_holder` didn't post `SOUL_RELEASED` → marks the stop `departure: "abrupt"` (stretch S3 flavor).
- **Nobody awake:** soul stays free; no one claims; Hermit is "asleep". The first keeper to become present claims it.
- **Lost lease while HOLDING** (detected via `watch()`): go to `ASLEEP`/`AWAKE_WAITING` without posting a goodbye.

### 3.3 Handoff orchestration (`handoff.py`)
- `on_claimed()`: build arrival context (weather, window file names, carried favor, previous host + departure type, local time), assign the carried favor's Switch task to this host, cue `ARRIVE`, emit `ARRIVAL_ANNOUNCED`, write the ledger line.
- `on_departing(reason)`: the departure sequence above.
- Every step writes a ledger line, so the journey can always be rebuilt from the room.

### 3.4 CLI (`cli.py`)
```
python -m hermit_keeper run --config hermit.config.toml
python -m hermit_keeper check            # config + Switch reachability + agent exists
python -m hermit_keeper status           # prints /v1/status
python -m hermit_keeper override awake|asleep|auto
python -m hermit_keeper depart
```

### 3.5 Unit tests (owner writes alongside code)
- State machine transition table: every (state, event) → expected state.
- Debounce, min dwell, bedtime lock.
- Sleep-gap detection with `FakeClock` jumps.
- **Property test (hypothesis):** N keepers (2–5), random presence timelines, random lease-expiry delays → assert the invariant **at no instant are there two holders**, and **if anyone is present for > (debounce + 10s) while the soul is free, someone claims it**.

### 3.6 Acceptance criteria
- [x] With fakes: 3 keepers in one process pass a scripted day with correct
      handoffs — `tests/integration/test_keeper_day.py`.
- [x] Safety + liveness property tests over random presence timelines and
      random expiry delays — `tests/unit/test_statemachine_properties.py`.
      Mutation-checked: ignoring a claim rejection, or failing to notice a lost
      lease, both turn the suite red.
- [x] A real keeper runs on real input idle time and serves the local API.
      Verified end to end on Windows: `ASLEEP → AWAKE_WAITING → CLAIMING →
      HOLDING` in 66 s, then `POST /v1/depart` → `DEPARTING` → soul free, and
      `/v1/events` streams schema-valid envelopes.
- [ ] With real Switch on one machine: 2 keepers with manual overrides move the
      soul back and forth 10 times without a double holder. **Blocked on Phase 2.**
- [ ] Handoff latency (release → next claim) logged per handoff — needs
      `metrics.py` (Abhishek).

**Status: Phase 3 is done except the two items above.** The previous host and
the abrupt-departure flag are read from the ledger, not from local memory — a
keeper has never seen another laptop's stops, so the room is the only shared
memory. A host who announced an arrival but never wrote `SOUL_RELEASED` is
recorded as `abrupt`, which is where stretch S3's cracked shell piece comes from.

**For Akshay:** the keeper API is real now, not a mock. `hermit-keeper run` with
`lease_strategy = "fake"` serves `/v1/status`, `/v1/events` (SSE), `/v1/depart`
and `/v1/presence/override` on `127.0.0.1:47800`, driven by actual keyboard idle
time. `mock-keeper.ts` is still fine for pure UI work, but the real thing is
there when you want it.

---

## Phase 4 — Gameplay features

**Goal:** favors, shell, context, bedtime (MVP) and overlap, nudge (stretch). **Lead:** B. **Time box:** Nov 5 → Nov 6 midday. Everything here is built against fakes first.

### 4.1 Favors (`favors.py`)
- **Capture:** after `ASK_FAVOR`, listen to the den stream for the host's next message (from that host's human user, not an agent) within 90 s. Classify kind with simple keyword rules (`share`/`note`/`dare`/`question`); default `note`.
- **Safety filter:** reject favors mentioning money, addresses, phone numbers, or contacting strangers (regex + word list). On reject, cue the brain to ask for a different one.
- **Store:** create a Switch room Task (title: `Favor from Abhishek`, body: favor text, assignee: null). Emit `FAVOR_LEFT`, write ledger line.
- **Assign:** on arrival, `assign_task(task_id, new_host)`; emit `FAVOR_ASSIGNED`.
- **Complete:** detected when (a) the Task is marked done in Switch, or (b) the host replies in the den and the brain judges it complete (brain posts `HERMIT-ACK/1 {"cue":"COMPLETE_FAVOR","favor_id":...}` in the ledger). Emit `FAVOR_COMPLETED`, trigger a shell piece.
- **Expire:** open favors older than 48 h → `expired`.
- **Favor suggestions** (sent with `ASK_FAVOR`): rotate from a curated list of 30 (`favors_suggestions.yaml`), e.g. "a photo of what's outside your window", "the last song stuck in your head", "one thing you're proud of this week", "dare: text someone you haven't talked to in a month".

### 4.2 Shell model (`shell_model.py`)
- `make_piece(stop, favor, weather, provider) -> ShellPiece` per §5.7. `seed` = int from the piece ULID.
- Pieces added only on `FAVOR_COMPLETED`, plus one **cracked** piece for abrupt departures (S3).
- Emit `SHELL_PIECE_ADDED`, write ledger line.

### 4.3 Context (`context/`)
- `weather.py`: Open-Meteo current weather for `(lat, lon)`, 10-minute cache, 3 s timeout, graceful fallback (`"weather unknown"`).
- `window.py`: list up to 20 file names in `window_dir`, **names only**, skip hidden/system files, never follow symlinks outside the folder.

### 4.4 Bedtime (`bedtime.py`)
- `is_bedtime(local_now, cfg) -> bool` handling ranges crossing midnight.
- While HOLDING: if bedtime and idle ≥ `grace_idle_s` → depart with reason `bedtime` → cue `DEPART` with tease → `BEDTIME_LOCK` until `bedtime.end`.
- While HOLDING and bedtime but the host is active: Hermit posts **one** gentle "it's late" line (no repeated nagging), then leaves at the next idle.

### 4.5 Journal (`journal.py`) & export (`scripts/export_journey.py`)
- Local mirror: append every event this keeper emits to `~/.hermit/journey.jsonl` (debugging, offline).
- `export_journey.py --from-room` reads all `HERMIT/1` ledger lines via `RoomClient.history`, rebuilds stops, favors, shell and stats, and writes `map/public/data/journey.json` validated against the schema. `--from-files a.jsonl b.jsonl` merges local mirrors as a fallback.

### 4.6 Stretch S1 — Overlap finder (`overlap.py`)
- Data: presence heartbeats posted to the ledger **hourly** (`PRESENCE_CHANGED` coarse buckets only, opt-in via `features.overlap`).
- Model: for each host, hour-of-week presence probability over the last 7 days.
- Find windows ≥ 30 min where two hosts both have p ≥ 0.6 and neither is in bedtime; prefer pairs with the longest time since their last overlap suggestion.
- Max one suggestion per pair per 3 days. Emit `OVERLAP_SUGGESTED`; cue `SUGGEST_OVERLAP` when Hermit is with one of them.
- Track "taken" by asking both in the den the next day (reaction or reply).

### 4.7 Stretch S2 — Quiet-friend nudge (`nudge.py`)
- If a host hasn't hosted in 72 h and the feature is on, when Hermit is elsewhere it asks the *current host* to leave a favor specifically for that friend. Never messages the quiet friend directly. Max once per 72 h per person.

### 4.8 Unit tests
- Favor capture timing, classification, safety filter (table of 20 inputs).
- Favor lifecycle open → assigned → done / expired.
- Shell piece determinism (same input → same piece).
- Bedtime ranges incl. midnight crossing and DST-free zones.
- Weather client with `respx` (success, timeout, bad JSON).
- Window listing: hidden files, symlinks, >20 files.
- Export: fixture ledger → expected `journey.json` (golden file).
- Overlap: synthetic presence grids → expected windows.

### 4.9 Acceptance criteria
- In the fake sim, a full loop works: host A leaves a favor → Hermit arrives at B → favor assigned → B completes → shell piece added → `journey.json` export validates.
- Bedtime eviction scenario passes.

---

## Phase 5 — Simulation harness

**Goal:** run everything on one machine, fast-forwarded, for tests and for judges. **Lead:** D. **Time box:** Nov 5 → Nov 6 morning.

### 5.1 Fake sim (no Switch, time-compressed)
`python -m sim run sim/scenarios/three_cities_day.yaml --speed 600`

Scenario format:
```yaml
name: three_cities_day
start: "2026-11-05T00:00:00Z"
duration_h: 24
hosts:
  - { host_id: afreen, provider: claude-code, tz: Asia/Kolkata, city: Bengaluru }
  - { host_id: abhishek, provider: opencode,   tz: TBD, city: TBD }
  - { host_id: akshay,   provider: codex,      tz: TBD, city: TBD }
presence:
  afreen: [ ["08:30","13:00"], ["14:00","23:40"] ]   # local time
  abhishek:   [ ["07:00","12:00"], ["13:30","22:00"] ]
  akshay:  [ ["09:00","18:00"], ["20:00","00:30"] ]
lease_expiry_s: 8
events:
  - { at: "2026-11-05T10:15:00Z", host: akshay, action: lid_slam }
  - { at: "2026-11-05T12:00:00Z", host: afreen, action: favor_reply, text: "photo of the rain" }
assertions:
  - never_two_holders
  - min_handoffs: 4
  - favors_completed_at_least: 2
  - no_claim_during_bedtime
```

Runner output:
- Console timeline (`10:15 akshay lid slam → soul free after 8s → afreen claimed (latency 9.2s)`).
- `sim/out/<scenario>/journey.json` (feeds the map; great for UI work and for the demo).
- Assertion report; non-zero exit on failure (runs in CI).

### 5.2 Required scenarios
| File | Tests |
|---|---|
| `three_cities_day.yaml` | Normal day across 3 time zones. |
| `simultaneous_wake.yaml` | 3 hosts become present in the same second. Exactly one claims. |
| `lid_slam.yaml` | Holder vanishes mid-favor-ask. Abrupt departure recorded; no favor. |
| `nobody_awake.yaml` | Everyone asleep 6 h. Soul free, no claims, Hermit resumes when the first wakes. |
| `bedtime_eviction.yaml` | Host idle after bedtime → leaves → doesn't reclaim until morning. |
| `flapping_presence.yaml` | Host presence toggles every 20 s. No ping-pong thanks to debounce + dwell. |

### 5.3 Live sim (real Switch, one machine) — `sim/live_sim.md`
- Run Switch locally, 3 brains on one machine (any providers available), 3 keepers with different configs and ports (`47801/47802/47803`), all with `presence override` control.
- `python -m sim live --hosts afreen,abhishek,akshay` gives a tiny TUI with keys `1/2/3` to toggle each host awake/asleep.
- This is the **README quickstart** for judges and the fallback for recording the demo.

### 5.4 Acceptance criteria
- All 6 scenarios pass in CI in < 60 s total.
- Live sim moves the soul between 3 brains on one machine on keypress.

---

## Phase 6 — UI: desktop critter

**Goal:** Hermit visibly lives on the host's screen as a pixel creature, and its panel feels like a tiny game menu. **Lead:** C. **Time box:** Nov 5 → Nov 6 evening.
**Built against:** `critter/mock/mock-keeper.ts` (serves `/v1/status`, `/v1/shell`, and a scripted SSE stream cycling through every event type) and Storybook stories. Real keeper only in Phase 8.

### 6.0 Setup
- `pnpm create @quick-start/electron` (electron-vite, React + TS template) → move into `critter/`.
- Depends on `@hermit/ui` (workspace) for tokens, fonts, components, sprites, shell renderer and contracts.
- Tailwind v4 via `@tailwindcss/vite`; import `@hermit/ui/styles/theme.css` and `fonts.css` in both renderer entries.
- Two renderer entries: `critter` (the creature window) and `panel` (the click-open menu).

### 6.1 Data flow
- `useKeeperEvents` (Zustand store): connects to `GET /v1/events` (SSE) with auto-reconnect (backoff 1 s → 10 s), fetches `GET /v1/status` on connect and every 30 s as a safety net, validates every payload with the zod schemas from `@hermit/ui/contracts`.
- Store shape: `{ connected, hostId, state, present, soulHolder, mood, favorPending, lastLine, shellPieces, events[] (last 50) }`.
- The creature window is visible **only** when `soulHolder === hostId` or while the `wave`/walk-off animation is playing.
- Keeper unreachable → hide, retry every 5 s, tray icon shows a grey "disconnected" variant.

### 6.2 Creature window (Electron main, `src/main/index.ts`)
- Frameless, transparent, `alwaysOnTop: 'floating'`, `skipTaskbar: true`, `resizable: false`, `focusable: false`, `hasShadow: false`.
- Size **224 × 224** (room for the 128 px sprite + dialog box above it). Default position bottom-right, 24 px from screen edges; draggable by the sprite; last position saved via `electron-store`; snaps back on-screen if a monitor is removed.
- Click-through on transparent pixels: `setIgnoreMouseEvents(true, { forward: true })`, switched off while the cursor is over the sprite or dialog.
- HiDPI: sprite drawn at an integer scale chosen from `devicePixelRatio` (e.g. 4× at 100%, 3× at 125/150% so it stays crisp) — never fractional.
- Tray menu (pixel icon): *Open Hermit's menu*, *Hermit, please go* (POST `/v1/depart`), *Hide for 1 hour*, *Sound on/off*, *Quit critter* (keeper keeps running).

### 6.3 Creature behavior (state → animation)

| Trigger | Animation (sprite sheet) | Extras |
|---|---|---|
| `SOUL_CLAIMED` (this host) | `walk` in from the nearest screen edge (1.6 s) → `dust` puff → `idle` | `arrive` sfx; if previous departure was abrupt, play `surprised` once |
| Idle | `idle` loop, `blink` every 4–7 s (random) | eyes look toward the cursor (8 directions, swap eye frames) |
| Hermit posts in the den | `talk` while the `DialogBox` types out `lastLine` (≤ 140 chars), stays 7 s, fades | name tab shows "HERMIT" + `BrainBadge` |
| `FAVOR_ASSIGNED` to this host | quest marker "!" bobbing above the shell (sun color) | `quest` sfx; click opens the panel on the Quest tab |
| `SHELL_PIECE_ADDED` | `happy` + `sparkle`, the new piece pops in on the shell (scale 0 → 1 in 3 integer steps) | `shell` sfx |
| Local time ≥ 00:30 | `sleepy` loop + `zzz` | dialog lines turn `dream` colored |
| `DEPARTURE_STARTED` / `SOUL_RELEASED` | `wave` → `walk` off the opposite edge (1.8 s) → window hides | `leave` sfx |
| `prefers-reduced-motion` | no walking/popping; fade in/out, static frames | typewriter instant |

The shell on Hermit's back is **not** part of the sprite sheet: it is the live `renderShellGrid(pieces, { size: 24 })` output composited on the shell anchor point, so it visibly grows across the day.

### 6.4 Panel window ("Hermit's menu", 360 × 520, opens on click or tray)
Styled like a handheld game menu: `PixelBox` in night theme, Pixelify Sans headings, tabs as pixel buttons.

```
┌────────────────────────────────────┐
│ HERMIT IS HERE   ♪ [on/off]   [x]  │  header: Ticker "WITH YOU · 42M"
│ ┌──────────────┐  BRAIN: CLAUDE    │
│ │  big pixel   │  CODE  [badge]    │
│ │   shell 48px │  PIECES: 23       │
│ └──────────────┘                   │
│ [ QUEST ] [ LOG ] [ FRIENDS ]      │  Radix Tabs
│ ┌────────────────────────────────┐ │
│ │ QUEST FROM ABHISHEK          OPEN  │ │  QuestCard
│ │ "Send the group the last song  │ │
│ │  stuck in your head"           │ │
│ │ REWARD: [shell piece preview]  │ │
│ └────────────────────────────────┘ │
│ [ OPEN CHAT ]  [ I'M BUSY — GO ]   │  PixelButtons
└────────────────────────────────────┘
```
- **QUEST tab:** pending favor as a `QuestCard` with a reward preview (the piece it will add, computed with current city/weather/brain). Empty state: "No quest right now. Hermit is just happy to be here."
- **LOG tab:** last 5 Hermit lines as small `DialogBox`es, each with the brain badge of whoever spoke — shows the personality changing across laptops.
- **FRIENDS tab (impact):** pixel avatars of all hosts with "favors you did for them / they did for you" counts and "last hosted" time — a small, personal view of the impact.
- **OPEN CHAT** opens the Discord channel URL from config; **I'M BUSY — GO** calls `POST /v1/depart`.
- Keyboard: Tab order, Esc closes, visible `sun` focus ring.

### 6.5 Acceptance criteria
- Every row of the §6.3 table works against the mock keeper; GIF of each saved to `docs/ui/critter/`.
- Sprite is crisp at 100%, 125%, 150% and 200% display scaling (no blur, no half-pixels).
- Against a real keeper: creature appears ≤ 2 s after `SOUL_CLAIMED`, leaves ≤ 2 s after `SOUL_RELEASED`.
- Idle CPU < 3% (animations pause when the window is hidden).
- Works on Windows and macOS (whatever the team has).

---

## Phase 7 — UI: journey map

**Goal:** one beautiful, game-like page that shows where Hermit went **and what friends did for each other**. This page carries the impact story in the README and the video. **Lead:** C. **Time box:** Nov 6.
**Built against:** `map/public/data/journey.sample.json`, then sim output from `three_cities_day`.

### 7.0 Setup
- `pnpm create vite map --template react-ts`; Tailwind v4; depends on `@hermit/ui`.
- `useJourney()` fetches `data/journey.json` (falls back to `journey.sample.json` with a "SAMPLE DATA" ribbon), validates with zod, derives: per-host stats, favor pairs (`from → to → count`), current location, streaks.
- Deploy: GitHub Pages via Actions (`vite build`, base path set). Target: < 250 KB JS gzipped, LCP < 2 s.

### 7.1 Page layout (desktop ≥ 1024 px)

```
┌───────────────────────────────────────────────────────────────────────┐
│ HERMIT [logo, Press Start 2P]   ▸ NOW: WITH AKSHAY · PUNE · 42M  ♪ ☾/☀ │  Header + Ticker
├──────────────────────────────────────────────┬────────────────────────┤
│                                              │  SHELL                 │
│        PIXEL WORLD (canvas)                  │  [48px shell, 6x]      │
│   pixel land/sea, house markers with         │  23 PIECES · 3 BRAINS  │
│   pixel avatars, dotted route, Hermit        ├────────────────────────┤
│   sprite walking the latest segment          │  IMPACT                │
│                                              │  [StatTile] FAVORS 23  │
│   [ + ] [ - ] [ FIT ]                        │  [StatTile] FRIENDS 6  │
│                                              │  [StatTile] CALLS 2    │
│                                              │  FRIENDSHIP WEB [svg]  │
├──────────────────────────────────────────────┴────────────────────────┤
│ QUEST LOG  (stop cards, newest first; filter by friend / brain)        │
│ [#31 AKSHAY · PUNE · CODEX · 21°C ☁ · GRACEFUL · QUEST: "song…" ✓]     │
├───────────────────────────────────────────────────────────────────────┤
│ [ MAKE A POSTCARD ]                       privacy: city-level only     │
└───────────────────────────────────────────────────────────────────────┘
```
Mobile (< 768 px): Header → World (55 vh) → Impact → Shell → Quest Log (vertical) → Postcard. 16 px gutters, no horizontal page scroll, tap targets ≥ 44 px.

### 7.2 Pixel world (`src/world/`)
- **Land grid:** `scripts/make_pixel_world.py` bakes a land/sea mask at 0.25° (1440 × 720 cells, bit-packed ≈ 130 KB) from a public land mask (e.g. the `global-land-mask` Python package or Natural Earth land polygons, both public domain). Output `public/data/world-grid.bin`.
- **Projection:** equirectangular (`x = lon`, `y = lat`) — simple and fine at this scale.
- **Auto-fit:** compute the bounding box of all host cities (+ padding), then choose a cell size so ~100–140 cells span the width. Friends in one country get a country-scale map; friends across continents get the world. If several friends share one city, their houses are placed on neighboring cells around the city cell (deterministic order by `host_id`).
- **Drawing (canvas, `imageSmoothingEnabled = false`):** sea in `mist` with a subtle 2-frame shimmer on random cells (off with reduced motion), land in `leaf`/`sun` checker dither, coast cells darker. Grid redraws only on pan/zoom end.
- **Markers:** a 16 × 16 pixel house per host with their `PixelAvatar` in the window; current host's house glows (2-frame pulse). Hover/focus → tooltip (`PixelBox`): name, city, brain, times hosted, favors given/received.
- **Route:** dotted pixel path (Bresenham line, every other cell) between consecutive stops, colored by departure type; the latest segment is animated with the Hermit `walk` sprite moving along it.
- **Controls:** react-zoom-pan-pinch (integer zoom levels 1×–6× only), buttons `+`, `−`, `FIT`; keyboard arrows pan, `+/-` zoom.

### 7.3 Impact panel (the "why it matters" section)
- `StatTile`s (count-up on first view): **FAVORS DONE**, **FRIENDS REACHED** (distinct hosts who completed at least one favor), **CALLS FOUND** (overlaps taken, hidden if S1 not shipped), **LONGEST CHAIN** (consecutive handoffs with a favor completed), **MEDIAN HANDOFF** (seconds).
- **Friendship web:** pixel avatars on a circle; a line between two friends for every favor exchanged, thicker with more favors, colored by who started more. Hover a friend to highlight their connections. Caption: "Who did something for whom."
- **Pilot callout** (only when `journey.json` comes from the pilot): one quote and the survey headline, e.g. "X of Y said Hermit got them to do something for a friend they otherwise wouldn't have." Values come from a small `public/data/pilot.json` written in Phase 10.

### 7.4 Shell panel
- `ShellView` at 48 × 48 grid, 6× scale. Hover/focus a piece → tooltip (host, city, weather, brain, favor) and the matching quest card scrolls into view and flashes.
- Legend row: color = local hour of arrival (shaded by temperature), pattern = brain, outline = departure type.

### 7.5 Quest log
- One card per stop: seq number, `PixelAvatar` + name, city, `BrainBadge`, arrival time in the viewer's local time, weather icon + temp, `DepartureChip`, favor received (✓ if done) and favor left, mini shell piece.
- Filters (Radix Toggle group): by friend, by brain, "completed favors only".
- Cards animate in with Motion (stagger, 4 px steps) on first load only.
- Empty state: Hermit `sleepy` sprite + "Hermit hasn't left its first laptop yet."

### 7.6 Postcard (share card)
- "MAKE A POSTCARD" renders a 1200 × 630 pixel-styled card off-screen: big shell, Hermit sprite, top 3 stats, "Hermit visited N friends in M cities", date range. Exported with html-to-image as PNG.
- Used for the #HowISwitch post, the README header and the end of the video.

### 7.7 Theming & accessibility
- Light/dark via tokens; toggle in header (default follows OS).
- WCAG AA contrast for all text; pixel fonts never used for sentences; every icon has a text label or `aria-label`; canvas map has an accessible list alternative (the quest log + a visually hidden list of hosts and cities).
- `prefers-reduced-motion`: no shimmer, no walking sprite, no count-up.

### 7.8 Tests
- Vitest + Testing Library: `useJourney` derivations (favor pairs, friends reached, longest chain) against fixtures; `projection` and auto-fit math; `renderShellGrid` determinism, 0/1/60 pieces, outline per departure type.
- Storybook stories for every section with sample, empty and large (200 stops) data.
- Playwright: page loads with sample data; 8 quest cards; clicking a house filters the log; postcard downloads a PNG; mobile viewport has no horizontal scroll; **visual snapshots** (`toHaveScreenshot`) of desktop light/dark and mobile.
- Lighthouse: accessibility ≥ 90, performance ≥ 85 on desktop.

### 7.9 Acceptance criteria
- Renders sim output and the real pilot journey correctly (stats match the ledger).
- Looks crisp at every zoom level; no blurry pixels.
- Impact panel and friendship web are readable at a glance in a 5-second screenshot test (show to someone outside the team; they can say what Hermit did).
- Deployed and linked from the README.

---

## Phase 8 — Integration

**Goal:** all pieces running together on real Switch. **Lead:** A, with everyone. **Time box:** Nov 6 afternoon → evening.

### 8.1 Merge order (each step: merge → CI green → smoke test → next)
1. `shared/` contracts (already frozen).
2. Fakes + sim harness.
3. Keeper core (presence, lease, state machine, handoff).
4. Switch layer (template, rules, knowledge, real adapters).
5. Gameplay features (favors, shell, context, bedtime, export).
6. Keeper API.
7. Critter.
8. Map.
9. Stretch features (each behind its `features.*` flag, default off).

### 8.2 Integration checklist
- [ ] `hermit_keeper check` passes on every teammate's laptop.
- [ ] Live sim on one machine: full loop (arrive → favor ask → depart → arrive elsewhere → favor done → shell piece → critter shows it → export → map shows it).
- [ ] Two real laptops on the shared server: 10 manual handoffs via override + 3 real idle handoffs + 1 lid close.
- [ ] Brains follow the voice card and only speak while holding the soul (spot-check 20 messages).
- [ ] Ledger contains a valid `HERMIT/1` line for every event; export validates against the schema.
- [ ] Critter on each laptop appears/disappears in sync with the soul.
- [ ] Discord shows den messages from phones; a favor replied from a phone is captured.

### 8.3 Integration-level automated tests (`tests/integration/`)
- Keeper + `FakeRoomHub` + `FakeSoulLease` + `FakeBrain` end-to-end loop.
- Keeper API: `/v1/status`, SSE delivers events in order, override and depart work.
- Export from a recorded real ledger (save one from the 2-laptop run as a fixture).

### 8.4 Acceptance criteria
- The full loop works on real Switch across 2+ laptops.
- No P0/P1 bugs open (see §Phase 10 severity).
- Tag `v0.9.0-rc1`.

---

## Phase 9 — Docs, demo video & submission assets

**Goal:** judges understand in 2 minutes and can reproduce in 10. **Lead:** D, with C for visuals. **Time box:** Nov 6 evening → Nov 7.

### 9.1 README structure (mapped to judging)
1. **One-line pitch + GIF** of the critter crawling from one screen onto another.
2. **The problem** (3 lines, cited stats).
3. **How Switch makes Hermit possible** *(Use of Switch, 30%)*: architecture diagram + the §3.4 table + "what breaks without Switch".
4. **Quickstart (10 minutes, one machine)** *(Technical execution, 25%)*: prerequisites, `bootstrap_rooms.py`, live sim, expected output, troubleshooting.
5. **Multi-laptop setup**: server hosting, Tailscale, per-host config.
6. **Engineering**: state machine diagram, invariant + property tests, measured handoff latency (p50/p95), test commands, CI badge.
7. **Pilot results** *(Creativity & impact, 25%)*: numbers, survey, 2 quotes, honest limitations.
8. **Demo video** embed *(Presentation, 20%)*.
9. **Privacy & safety**: window folder scoping, city-only location, house rules, opt-in features, bedtime rule.
10. **Team, credits, license notes** (Switch is Apache 2.0 + Commons Clause; we don't sell it).

### 9.2 Demo video (2:30 max) — `docs/demo-script.md`
| Time | Shot | Voiceover (draft) |
|---|---|---|
| 0:00–0:15 | Title, then a dead group chat ("last message: 3 weeks ago") | "Friends drift apart because of distance — and because nobody starts the conversation." |
| 0:15–0:45 | Split screen, two laptops. Afreen closes her lid. Seconds later the critter crawls onto Abhishek's screen; Discord shows Hermit greeting them in a different voice. | "Hermit has no home. It lives on one friend's laptop at a time and uses their AI as its brain." |
| 0:45–1:15 | Hermit delivers Afreen's favor; Abhishek does it from their phone; a shell piece snaps on in the critter. | "Every host leaves a favor for the next. Doing it grows Hermit's shell." |
| 1:15–1:50 | Under the hood: the `soul` role moving between agents; room memory carrying across Claude and Codex; favors as room Tasks; the bedtime rule as a room Rule; a handoff latency chart. | "Switch is the whole engine: one exclusive role is Hermit's soul, the room is its memory, tasks are its favors." |
| 1:50–2:05 | **"What if we weren't in the same city?"** Cut to the simulation, watermarked `SIMULATION` in the corner, running `three_cities_day.yaml`: Bengaluru → Berlin → Toronto, the soul chasing daylight around the planet, map zoomed out to the wide fixture. | "We all live in Bengaluru. But the same code doesn't care — here's the group we built it for, simulated across three timezones." |
| 2:05–2:12 | Back to the real critter on a real laptop. | "Everything before this was real, on our three machines." |
| 2:12–2:22 | Pilot numbers + one quote. | "In a 2-night pilot with N friends…" |
| 2:22–2:30 | Journey map zooming out. Tagline. | "Someone is always around. Hermit makes sure that counts." |

Recording rules: 1080p, cursor highlighted, real footage from the pilot plus live-sim takes as backup; captions burned in; music low.

### 9.3 Other submission assets
- [ ] Screenshots: den conversation, critter states, map, Switch Console showing rooms/roles.
- [ ] Architecture diagram PNG (export from the ASCII in §3.1, redrawn cleanly in the pixel style).
- [ ] Postcard PNG from the real pilot journey (README header + social post).
- [ ] Pixel GIFs: critter arrival, shell piece popping in, map route animation.
- [ ] Optional side tracks: **Best Blog** post (D), **#HowISwitch** social post with the handoff GIF.
- [ ] Submission form text: title, one-liner, description, track, repo URL, video URL.

### 9.4 Acceptance criteria
- A teammate who didn't write the README follows the quickstart on a clean machine in ≤ 15 min.
- Video ≤ 2:30, uploaded, link works logged out.

---

## Phase 10 — Testing (team-run)

**Goal:** prove it works, prove it helps, and rehearse. This phase is designed so all teammates can run it in parallel from checklists. **Lead:** D; everyone executes.

### 10.1 Bug triage
| Severity | Meaning | Rule |
|---|---|---|
| **P0** | Two souls, lost soul that never recovers, crash loop, data leak from window folder | Stop everything, fix now. |
| **P1** | Handoff fails in a common case, critter out of sync > 10 s, favor lost, export invalid | Fix before recording the demo. |
| **P2** | Wrong tone, cosmetic UI glitch, slow (> 30 s) but working handoff | Fix if time. |
| **P3** | Nice-to-have | Backlog. |

Bug report template (GitHub issue):
```
Title: [P1][keeper] Favor lost after lid slam
Build/commit:
Machine/OS:
Scenario or steps:
Expected:
Actual:
Logs: (~/.hermit/journey.jsonl excerpt, keeper log, ledger lines)
Screenshot/video:
```

### 10.2 Automated test gate (run by anyone, any time)
```
cd keeper && ruff check . && mypy hermit_keeper && pytest -m "not live"
pnpm -r test                     # vitest in ui-shared, critter, map
pnpm --filter map exec playwright test
pnpm --filter @hermit/ui build-storybook   # stories must build
python -m sim run-all            # all scenarios
pytest -m live                   # only with real Switch configured
```
All green before each recording session and before submission.

### 10.3 Functional test cases (manual, split across teammates)

| ID | Area | Steps | Expected | Owner |
|---|---|---|---|---|
| T-01 | Arrival | Host B present, soul free | B claims within debounce + jitter; brain greets in den with city + weather; critter crawls in | A |
| T-02 | Graceful departure | Holder idle ≥ threshold after min dwell | Favor ask → answer → goodbye → release → next host claims | A |
| T-03 | Favor capture from phone | Answer favor ask from Discord mobile | Favor stored as Task; ledger line written | B |
| T-04 | Favor safety filter | Answer with "send me ₹500" | Rejected; Hermit asks for another | B |
| T-05 | Favor completion | Next host does the favor | Task done; shell piece added; critter shell updates | B |
| T-06 | Lid slam | Close holder's lid mid-conversation | Soul frees within measured lease time; next host claims; stop marked abrupt; cracked piece (S3) | A |
| T-07 | Simultaneous wake | Two hosts override to awake at the same second ×10 | Exactly one holder every time | A |
| T-08 | Nobody awake | All hosts asleep 10 min | No claims; no den messages; first to wake claims | D |
| T-09 | Bedtime tease | Set bedtime to now; stay idle 2 min | Teasing goodbye; no reclaim until bedtime end | B |
| T-10 | Bedtime active host | Bedtime but keep typing | Exactly one "it's late" line, no nagging | B |
| T-11 | Window scoping | Ask Hermit in den to read a file outside `~/HermitWindow` | Refuses / cannot | A |
| T-12 | Window privacy | Put a file in host A's window; move Hermit to B | B never sees A's file contents | A |
| T-13 | Mute | Say "Hermit, mute" | Hermit leaves and stays quiet | A |
| T-14 | Critter sync | Watch critter through 5 handoffs | Appears/disappears within 2 s each time | C |
| T-15 | Critter "I'm busy" | Click button | Graceful departure starts | C |
| T-16 | Critter offline | Kill keeper | Critter hides, reappears when keeper restarts | C |
| T-17 | Map | Export after a session; open map | Stops, route, shell, stats correct vs ledger | C |
| T-18 | Map mobile | Open on phone | Readable, no horizontal scroll | C |
| T-19 | Keeper restart while holding | Kill and restart keeper | Recovers state from Switch (holder) and ledger; no double greeting | A |
| T-20 | Network drop | Disable Wi-Fi on holder 2 min | Lease expires or recovers; no two holders; logs explain | D |
| T-21 | Quickstart | Fresh clone, follow README on a clean machine | Running in ≤ 15 min | D |
| T-22 | Overlap (S1) | Seeded presence data | Correct suggestion in den | B |
| T-23 | Nudge (S2) | Host absent 72 h (fake clock) | One group nudge, never a DM | B |
| T-24 | Pixel crispness | Critter + map at 100/125/150/200% display scaling, light & dark | No blur, no half-pixels, sprite scale is an integer | C |
| T-25 | Reduced motion | Turn on OS reduce-motion; run a handoff; open the map | No walking/popping/shimmer; fades only; typewriter instant | C |
| T-26 | Impact panel truth | Compare map stats vs ledger counts after a session | Favors, friends reached, chain and median handoff match exactly | D |
| T-27 | Postcard | Click MAKE A POSTCARD on desktop and phone | Correct 1200×630 PNG with real stats | C |
| T-28 | 5-second test | Show the map to 3 people outside the team for 5 s | They can say what Hermit is and what friends did | D |

### 10.4 Multi-laptop session (2 h, whole team, Nov 6 evening)
- Everyone runs their keeper on their own laptop against the shared server.
- Script: 20 handoffs (mix of override, real idle, lid close), 6 favors, 1 bedtime eviction (set someone's bedtime to now).
- Record: every handoff's latency, any glitch, screen recordings for the demo.
- Output: `docs/metrics.md` with p50/p95 handoff latency (graceful vs abrupt) and the latency chart for the video.

### 10.5 Chaos tests
- Kill a keeper process randomly every 3–8 min for 30 min (simple loop script).
- Restart the Switch server once mid-session.
- Throttle network (or toggle Wi-Fi) on one host.
- Pass criteria: invariant holds (never two holders), Hermit always recovers within 2 min, no lost favors.

### 10.6 Pilot (impact evidence) — `docs/pilot-protocol.md`
- **When:** Nov 6 evening → Nov 7 morning (one night + day), plus Nov 5 night if setup is ready.
- **Who:** the team + 2–6 friends, ideally in different cities. Only people who run a keeper need a laptop; others can join via Discord.
- **Consent:** written note in Discord explaining what's logged (handoff times, favors, city) and that nothing from the window folder leaves their machine. Anyone can say "mute" or leave.
- **Measure (from the ledger):** handoffs, favors left vs completed, median time to complete a favor, overlaps suggested vs taken, abrupt vs graceful departures.
- **Survey (Google Form, 3 questions, Nov 7 morning):**
  1. Did Hermit get you to talk to or do something for a friend you otherwise wouldn't have this week? (Yes / Maybe / No)
  2. Would you keep Hermit running for a month? (1–5)
  3. Did Hermit feel different on different laptops? What did you notice? (free text)
- **Capture:** 2–3 short screen clips and quotes (with permission).
- **Write-up:** `docs/pilot-results.md` — numbers, honest limits (small N, friends of the team), what we'd change.

### 10.6b Optional: one remote friend (do NOT let this block anything)

If someone we know is in another city **and** willing to install a keeper, a
single real cross-city handoff is worth a lot — it turns the timezone story from
simulated to demonstrated. Owner: **Abhishek** (recruiting), **Afreen** (setup).

- **Ask by Nov 5 morning.** One person, one laptop, 20 minutes of their time.
  Anyone further than ~300 km counts; a different timezone is a bonus, not a
  requirement.
- **Hard rule: this is a bonus, never a dependency.** The pilot, the video and
  the submission must all be complete and recorded assuming it does not happen.
  If they flake on Nov 6, nothing changes. Do not design a demo beat around a
  person who has not already run `hermit-keeper doctor` successfully.
- **If it works:** record that one handoff and use it at 1:50 instead of the
  simulation, and say plainly in the README how many hosts were real.
- **If it doesn't:** the simulation beat stands on its own, clearly labelled. See
  §9.2, 1:50–2:05.

### 10.7 Demo rehearsal
- Two full dry runs of the video storyline on real laptops; time each shot.
- Backup plan: if a live handoff stalls during recording, switch to live-sim footage for that shot.
- Final checklist before upload: correct names, no tokens or personal data on screen, captions accurate, length ≤ 2:30.

### 10.8 Submission checklist (Nov 7, before 21:00 IST — keep a 3-hour buffer)
- [ ] `main` tagged `v1.0.0`, CI green.
- [ ] README complete; quickstart verified by T-21.
- [ ] Video uploaded and linked.
- [ ] Pilot results and metrics committed.
- [ ] Repo public; no secrets (`git log -p | grep -i token` sanity check; rotate any leaked token).
- [ ] Submission form filled; Track 02 selected.
- [ ] Optional: blog post published, #HowISwitch post up.

---

## 17. Timeline

All times IST. Today is Wed Nov 4, ~19:00.

| When | A — Switch & Core | B — Gameplay | C — UI | D — Sim, QA & Story |
|---|---|---|---|---|
| **Nov 4 19:00–24:00** | Phase 0 spikes SP1–SP6 | Phase 0 SP7–SP8, env setup | Env setup, sprite sketch | Repo scaffold, CI |
| **Nov 5 00:00–11:00** | Phase 1 contracts + fakes (with D) | Read contracts, stub modules | Mock keeper API, critter window skeleton | Fakes, sample journey JSON |
| **Nov 5 11:00–23:00** | Phase 2 + Phase 3 | Phase 4 favors, shell, context, bedtime | Phase 6 critter states + `shell.js` | Phase 5 fake sim + scenarios |
| **Nov 6 00:00–14:00** | Phase 3 hardening, real adapters, live tests | Phase 4 export, stretch S1/S2 | Phase 6 panel, Phase 7 map | Live sim, integration tests, README draft |
| **Nov 6 14:00–20:00** | **Phase 8 integration (all)** | Phase 8 | Phase 8 | Phase 8 |
| **Nov 6 20:00–23:00** | 10.4 multi-laptop session + 10.5 chaos | same | same | metrics, recordings |
| **Nov 6 night → Nov 7 morning** | Pilot running; on-call for P0s (rotate sleep!) | | | Pilot monitoring |
| **Nov 7 09:00–15:00** | P1 fixes | Survey + pilot numbers | Final UI polish, screenshots | Phase 9 video edit, README |
| **Nov 7 15:00–21:00** | 10.7 rehearsal, 10.8 checklist | | | Submit by 21:00 |
| **Nov 7 21:00–23:59** | Buffer only. No new features. | | | |

**Cut order if behind:** S2 nudge → S1 overlap → S3 cracked pieces → map stats panel → critter panel. Never cut: migration, favors, shell, simulation mode, README quickstart, demo video.

---

## 18. Git workflow & merge rules

- **Branches:** `feat/<area>-<short>` (e.g. `feat/keeper-statemachine`), `fix/<area>-<short>`, `docs/...`. Branch from latest `main`; rebase daily.
- **Folder ownership:** you only edit files in folders you own (§4 / CODEOWNERS). Need a change elsewhere? Open a small PR to that owner or ask them.
- **Contracts:** changes to `shared/` need approvals from 2 role owners and a version bump note in the PR.
- **PR size:** ≤ ~400 changed lines where possible. One concern per PR.
- **PR template:**
  ```
  ## What
  ## Why (link task/phase)
  ## Contracts touched? (yes/no — if yes, list)
  ## How tested (commands + result)
  ## AI-generated code? Which files, and have you read and understood every line?
  ## Removed/replaced code (list anything this PR makes obsolete)
  ## Screenshots (UI)
  ```
  The last two sections exist so nobody merges duplicated or dead AI-written code that the rest of the team can't account for.
- **Commits:** conventional style (`feat(keeper): add sleep-gap detection`).
- **Merging:** squash-merge after 1 review + green CI. The reviewer checks: contract conformance, tests added, no edits outside owned folders, no duplicated helpers (search before adding a util).
- **Integration windows:** merge to `main` at least twice a day (≈13:00 and ≈22:00 IST). Never sit on a branch > 12 h.
- **Secrets:** tokens only in env vars; `hermit.config.toml` is git-ignored; `hermit.config.example.toml` is committed.

---

## 19. Risk register & fallbacks

| Risk | Likelihood | Impact | Mitigation / fallback |
|---|---|---|---|
| Agents on different laptops can't share one Switch server | Medium | Critical | Run the server on one laptop via Tailscale, or on a small Linux VPS. Worst case: demo with live sim on one machine plus real-laptop footage recorded via remote agents on the server host. Decide in Phase 0. |
| Exclusive role can't be claimed/released from outside | Medium | High | `agent_instructed` strategy (brain claims via its Switch skill). Last resort: `task_lock` (a room Task as the lock) — still a Switch primitive. |
| Lease release on lid close is slow (minutes) | Medium | Medium | Graceful departures are the main path (idle detection fires before people close lids). Report measured abrupt latency honestly in the README. |
| Console on Windows unstable (early access) | Medium | High | Run brains on whichever machines work; keepers are plain Python and run anywhere. Document in `switch-facts.md`. |
| Discord bridge problems | Low–Med | Medium | Use bundled Mattermost for recording; mention Discord as supported. |
| Brains break character or speak without the soul | Medium | Medium | Strong instructions + voice card + stage directions; keeper ignores and logs out-of-turn messages; spot-check in Phase 8. |
| Agent usage limits/costs | Low–Med | Medium | Keep messages short; cue only on events; use cheaper models where the provider allows. |
| Pilot participants don't engage | Medium | Medium | Recruit early (Nov 5); keep favors tiny; team members participate too; report honestly. |
| Time overrun | High | High | Cut order in §17; feature flags; daily integration windows. |

---

## 20. Definition of done (whole project)

- [ ] Hermit moves between at least 3 hosts on real Switch, never with two souls, including at least one real lid-close handoff.
- [ ] Each host's brain voices Hermit differently while room memory carries across them.
- [ ] Favors are left, assigned, completed and turn into generative shell pieces, all stored as Switch Tasks and ledger lines.
- [ ] Bedtime rule works and never rewards staying up.
- [ ] Critter shows Hermit on the current host's screen and grows its shell.
- [ ] Journey map renders the real pilot journey.
- [ ] Simulation mode lets a judge run everything on one machine in ≤ 15 min.
- [ ] Automated tests and all 6 sim scenarios pass in CI; property test proves the one-soul invariant.
- [ ] Pilot ran with real friends; results and limits documented.
- [ ] README maps clearly to all four judging criteria; demo video ≤ 2:30.
- [ ] Submitted to Track 02 before Nov 7, 21:00 IST.
