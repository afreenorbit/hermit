# Live test — three laptops, one Hermit

The runbook for the real test. Follow it top to bottom; nothing here is
optional until the section that says it is.

**Read this first:** two things are **not built yet** and must be done before
the test can happen. They are Step 1 and Step 2 below, and they are Afreen's.
Everything after that is setup anyone can do.

| | Who | When |
|---|---|---|
| Step 1 — real rooms and ledger | Afreen | before the test |
| Step 2 — the soul role | Afreen + one brain | before the test |
| Step 3 — the server everyone reaches | Afreen | before the test |
| Step 4 — each laptop | everyone | on the day |
| Step 5 — the test itself | everyone | on the day |

---

## Where we actually are

Phases 0–7 are built. Switch runs locally and a keeper agent registers against
it. **But Hermit still runs on fakes** — every keeper uses
`lease_strategy = "fake"`, so today you could delete Switch and Hermit would
behave identically. Steps 1 and 2 are what change that.

Be honest about this in the README until it is done.

---

# Step 1 — Hermit's memory really lives in Switch

**Owner: Afreen. Nothing blocks this.**

Right now the ledger is a Python dict. After this it is a Switch room, and
killing the server visibly stops Hermit.

1. Bring the stack up (it is already configured):

   ```bash
   cd ../switch-826
   ```

   ```bash
   docker compose -f deploy/local/standalone-v0.9.0.yml --profile collab --profile gateway --project-directory . up -d
   ```

   Check all five are healthy: `docker ps --filter name=hermit-switch`.
   Switch API on `:8000`, gateway `:3000`, Mattermost `:8065`.

2. Register the three keeper agents. One `POST /agents` each, with
   `Authorization: Bearer $AGENT_REGISTRATION_TOKEN` from `switch-826/.env`.
   The body shape is in `docs/switch-facts.md` under "The handshake".
   **Each returns its own `api_key` — that is the credential the keeper uses
   from then on, not the registration token.**

3. Create `hermit-den` and `hermit-ledger` on the server, and keep the room ids.

4. Point the keeper's room client at real Switch: set
   `lease_strategy = "agent_instructed"` and `switch.server_url`, and export
   `HERMIT_SWITCH_TOKEN` with that host's `api_key`.

**Done when:** a keeper writes a `HERMIT/1 {...}` line that you can read back
out of `hermit-ledger`, and stopping the Switch container makes the keeper
visibly lose the group.

---

# Step 2 — the soul is a real Switch role

**Owner: Afreen, with one brain connected. Harder; do it after Step 1.**

This is the part that makes Hermit's identity come *from Switch* rather than
from our code — the strongest thing in the project.

1. Define the exclusive `soul` role in `hermit-den`, with the text of
   `switch/rules/hermit-identity.md` as its instructions.
   `python switch/scripts/bootstrap_rooms.py --dry-run` prints the exact call.

2. Connect one coding agent (Claude Code) to Switch through the Console, and
   put it in `hermit-den`. **`assume_role` is only reachable from a connected
   agent over MCP — there is no HTTP path for it** (switch-facts, verified).

3. Cue it with `CLAIM_SOUL` and confirm it calls `assume_role("soul")` and gets
   the role's instructions back.

4. **Measure the lease expiry.** Kill that agent's session and time how long
   until the role frees. Put the real number in `expiry_delay_s` and in the
   README — right now it is a guess of 8 s.

5. Rewire `AgentInstructedLease.holder()` to read the holder from the ledger.
   It currently calls `list_roles` over HTTP, which **does not exist** and will
   fail. Tracked in switch-facts.

**Done when:** two brains try to claim and Switch refuses the second.

---

# Step 3 — one server everyone can reach

**Owner: Afreen.** **Decided: the server runs on Afreen's laptop**, kept awake and
plugged in for the test. The click-by-click version of Steps 3 and 4, checked
against Switch's own docs, is [`switch-setup.md`](switch-setup.md).

The server must **not** be on a laptop that sleeps. If the machine hosting
Switch closes its lid, Hermit stops for everyone — which is the one failure
that makes the whole idea look broken.

Pick one:

- **A spare always-on machine** (desktop, old laptop, Pi with 4 GB) — free.
- **A small VPS** — about €0.50 for the hackathon. No sleep problem.

Then Tailscale, which is free for our size:

1. Make a Tailscale account. Everyone joins the **same tailnet** — one person
   creates it and invites the other two.
2. Install Tailscale on the server machine and all three laptops.
   `tailscale up` on each; sign in with the same account.
3. On the server: `tailscale ip -4` → note the `100.x.y.z` address. That is
   the address everyone uses.
4. The stack binds to `127.0.0.1` by default, so it is not reachable yet. Set
   `SWITCH_BIND_ADDR=0.0.0.0` in `switch-826/.env` and bring the stack back up.
   Tailscale, not the public internet, is what makes that safe — do not also
   forward the port on your router.
5. From another laptop: `curl http://100.x.y.z:8000/health` → `200`.

**Done when:** all three laptops get `200` from that address.

---

# Step 4 — each laptop

**Everyone does this on their own machine.** 20 minutes.

### 4.1 Your agent

| | brain | fallback |
|---|---|---|
| Afreen | Claude Code | OpenCode, Codex |
| Abhishek | OpenCode | Claude Code |
| Akshay | Codex | Claude Code |

Installed and logged in. One each, all different — that is the demo.

Then connect it to Switch with **Switch Console**
([releases](https://github.com/sandbox-quantum/switch/releases)). Choose *Add a server →
Connect to an existing server* with Gateway `http://100.x.y.z:3000` and API
`http://100.x.y.z:8000`, link your Mattermost account, and onboard your brain as
`hermit-<you>` with working directory `~/HermitWindow`.

> ⚠ Set **Who can talk to your agent → Anyone.** The default, *Only me*, makes
> the brain refuse cues from your keeper and messages from friends in the den, so
> Hermit goes silent with no error. Details in
> [`switch-setup.md`](switch-setup.md) B3.

`python scripts/hermit_setup.py <you> --server 100.x.y.z` writes your config and
checks everything in this step.

### 4.2 The repo

```bash
git clone https://github.com/afreenorbit/hermit.git && cd hermit
```

macOS/Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e "keeper[dev]"
```

Windows PowerShell — **note the `;`, not `&&`**:

```powershell
py -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e "keeper[dev]"
```

```bash
pytest keeper -m "not live" -q
```

Expect **121 passed**. Then:

```bash
corepack enable pnpm; pnpm install
```

### 4.3 Your config

```bash
cp hermit.config.example.toml hermit.config.toml
```

Fill in: `host_id` (afreen / abhishek / akshay), `display_name`, your **area**
(Indiranagar / Kengeri / Koramangala) and its lat/lon — **never your street
address** — `timezone = "Asia/Kolkata"`, your `brain_provider`, and your real
`bedtime`.

Then, once Step 3 is done:

```toml
[switch]
server_url     = "http://100.x.y.z:8000"
lease_strategy = "agent_instructed"
```

Export your own api_key (Afreen sends it to you privately — **not in the group
chat, and never committed**):

```bash
export HERMIT_SWITCH_TOKEN=<your api_key>
```

```bash
mkdir ~/HermitWindow
```

```bash
python -m hermit_keeper check
```

### 4.4 Start your keeper and critter

```bash
python -m hermit_keeper run
```

Leave it running. In a second terminal:

```bash
pnpm --filter @hermit/critter dev
```

> ⚠ **PowerShell:** `&&` is a parse error in Windows PowerShell 5.1 — use `;`.
> And never use `>>` to append to a config file: it writes UTF-16 and corrupts
> it. Use an editor.

---

# Step 5 — the test

Everyone's keeper running, everyone's critter on screen, and the dashboard open
on at least one machine.

### The dashboard

```bash
pnpm dev:map
```

Vite prints the port it chose — **read it from the terminal**, it is not always
5173. Then open:

```
http://localhost:<printed-port>/?live=http://127.0.0.1:47800
```

The `?live=` part is needed today; auto-discovery is not built yet. It only
accepts a loopback keeper, so point it at **your own** keeper — it will still
show all three laptops, because every keeper folds the same shared ledger.

The critter does **not** need this page open. It talks to its own keeper.

### What you should see

| Your mascot | Means |
|---|---|
| **visiting** | Hermit is on your laptop |
| **arriving** | you just got it (first 10 s), carrying a letter |
| **away** | it is leaving you |
| **sleeping** | you are idle, or past your bedtime |
| **waiting** | you are here, Hermit is with someone else |
| **offline** | your keeper is not reachable |

**Only one laptop is ever `visiting`.** If two are, stop and tell Afreen — that
is the one bug that matters.

### The runs

Do these in order and write down what each screen showed.

**Test 1 — the handoff.** One person works, one goes idle.
1. All three active. Note who has Hermit — all three screens should agree.
2. The host stops touching their laptop for `idle_threshold_s` (5 min default).
3. Watch: host goes `away` → `sleeping`; someone else goes `arriving` →
   `visiting`; the third stays `waiting` throughout.
4. **Check the dashboard names the new host**, and that the old one shows "away
   from the keyboard".

**Test 2 — talk to whoever has it.** Open the den in Mattermost (or Discord if
the bridge is up). Whoever has Hermit sees it speak in *their* agent's voice.
Someone else sends a message — Hermit answers from the host's laptop. This is
the point of the whole thing: you are talking to a creature that lives on your
friend's machine.

**Test 3 — the lid.** The host closes their laptop with no warning.
Expected: no goodbye, the lease expires, someone else picks it up, and the next
arrival records the previous stop as **abrupt**. Time how long the gap is —
that is the real expiry number.

**Test 4 — everyone away.** All three idle. Hermit should be *nowhere*: no
laptop `visiting`, all `sleeping`. It must not invent activity.

**Test 5 — bedtime.** Set one person's bedtime to a few minutes from now. Past
it, Hermit should leave them and not come back until morning, however awake
they are.

**Test 6 — a keeper dies.** One person Ctrl-Cs their keeper. The other two
should show that laptop as `offline` within ~35 s — **not** as sleeping. Start
it again; it should rejoin on its own.

**Test 7 — the favor chain.** The host leaves a favor on the way out; the next
host receives it on arrival and does it; a shell piece appears.

### Write it down

For each test: what each of the three screens showed, what the dashboard said,
and how long transitions took. That is the pilot data for the README, and the
footage for the video.

---

## If it goes wrong

| Symptom | Likely cause |
|---|---|
| Two laptops `visiting` | real bug — stop, screenshot, tell Afreen |
| Everyone `offline` | Switch unreachable; `curl http://100.x.y.z:8000/health` |
| Your mascot stuck `offline` | your own keeper died; check its terminal |
| Nobody ever gets Hermit | nobody is passing debounce — check `hermit-keeper check` |
| Hermit never leaves | `min_dwell_s` has not elapsed, or you keep touching the keyboard |

**Fallback if the server will not come up on the day:** run
`python -m sim live` on one laptop. Three keepers share one soul on three
ports, and all the mascot transitions work. It proves the behaviour, not the
network — label it as a simulation in anything you record.

---

## Answering the question we will be asked

> *Would the project stop working without Switch?*

After Steps 1 and 2: yes, visibly. Hermit's memory is a Switch room, its
identity is a Switch role, and only one agent can hold that role.

Before Steps 1 and 2: no. That is why they come first.
