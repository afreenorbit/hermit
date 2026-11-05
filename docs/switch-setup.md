# Switch setup: one server, three laptops

Owner: Abhishek (setup and testing). The server runs on **Afreen's laptop**.

This is the concrete version of Steps 3 and 4 of [`live-test.md`](live-test.md),
checked against Switch's own docs (`docs/official/` in the Switch repo). Follow it
top to bottom. Every value in `<angle brackets>` is filled in on the day and
**never committed**: no IPs, keys or tokens in git, screenshots or the group chat.

```
                 Tailscale tailnet (private, nothing on the public internet)
   ┌───────────────────────────────────────────────────────────────────┐
   │  AFREEN's laptop  (stays awake)                                   │
   │    Switch stack: API :8000 · Gateway :3000 · Mattermost :8065     │
   │    also a host: keeper-afreen + brain hermit-afreen (Claude Code) │
   └──────────────▲──────────────────────────────▲─────────────────────┘
                  │ 100.x.y.z                    │ 100.x.y.z
   ┌──────────────┴───────────┐     ┌────────────┴─────────────┐
   │ ABHISHEK                 │     │ AKSHAY                   │
   │ keeper-abhishek          │     │ keeper-akshay            │
   │ brain hermit-abhishek    │     │ brain hermit-akshay      │
   │ (OpenCode)               │     │ (Codex)                  │
   └──────────────────────────┘     └──────────────────────────┘
```

Each laptop runs **two Switch agents**:

| Agent | What it is | How it joins Switch |
|---|---|---|
| `keeper-<you>` | our Python keeper: presence, ledger, critter API | `POST /agents` with the registration token (custom connector) |
| `hermit-<you>` | your own coding agent, Hermit's brain | **Switch Console** → onboard agent (Claude Code / OpenCode / Codex) |

Only the brain can hold the `soul` role. `assume_role` exists only for an agent
connected through Switch's agent tools, which is why the brain is onboarded with
Switch Console rather than by our code (switch-facts SP2).

---

## Part A — the server (Afreen, once)

### A1. Keep the laptop awake

If this laptop sleeps, Hermit stops for everyone.

- **Windows:** Settings → System → Power → *When plugged in, put my device to sleep after* → **Never**.
  Control Panel → Power Options → *Choose what closing the lid does* → **Do nothing** (plugged in).
- **macOS:** `caffeinate -dimsu` in a terminal you leave open, plus System Settings → Battery →
  *Prevent automatic sleeping when the display is off*.

Keep it plugged in for the whole test.

### A2. Tailscale

1. Create the tailnet: <https://login.tailscale.com>, then install Tailscale and sign in.
2. Admin console → **Users → Invite users**. Invite Abhishek and Akshay by email.
3. On this laptop:

   ```bash
   tailscale ip -4
   ```

   That `100.x.y.z` is **the server address**. Send it to the other two privately.

### A3. Let the tailnet reach the stack

The stack binds to `127.0.0.1` by default, so only this laptop can reach it.
In the sibling `switch-826/.env`, bind only to Afreen's Tailscale IP:

```dotenv
SWITCH_BIND_ADDR=<100.x.y.z>
```

Then recreate it (the released compose file and the released image go together;
see switch-facts "Running it again"):

```bash
cd ../switch-826
```

```bash
docker compose -f deploy/local/standalone-v0.9.0.yml --profile collab --profile gateway --project-directory . up -d --force-recreate
```

**Do not forward any port on the router.** Keep the bind address restricted to
the Tailscale IP, not `0.0.0.0`.
On Windows, allow Docker through the firewall for *Private* networks if prompted.

Check from this laptop, using the Tailscale address rather than localhost:

```bash
curl http://<100.x.y.z>:8000/health
```

### A4. Mattermost accounts (the den lives here)

Open `http://<100.x.y.z>:8065`. Create an account for each of the three of you
and for every pilot friend, or let them sign up, and add everyone to the team.

### A5. Keeper registrations and rooms

**Already done on the current test server:** `keeper-afreen`, `keeper-abhishek`
and `keeper-akshay` are registered. Switch Console shows `#hermit-den` under
Mattermost and `hermit-ledger` under **No messaging app**, each with three
keeper agents. The rooms do not need to be recreated. The three `hermit-<name>`
coding agents are a separate B3 step on each person's laptop.

For a fresh server only, register the keepers as follows:

One `POST /agents` per keeper, with `Authorization: Bearer <AGENT_REGISTRATION_TOKEN>`
from `switch-826/.env`. The body is in [`switch-facts.md`](switch-facts.md) under
"The handshake". Use the names `keeper-afreen`, `keeper-abhishek` and `keeper-akshay`.

Each call returns `{id, api_key}`. **Send each person their own `id` and `api_key`
privately**, never in the group chat. The keeper uses its own key from then on,
not the registration token.

`switch/scripts/bootstrap_rooms.py` can do A5 and create the rooms, writing keys
only to git-ignored `.switch-agents.json`. Do not rerun it just to inspect the
existing rooms.

---

## Part B — each laptop (everyone, ~20 min)

### B1. Tailscale

Install from <https://tailscale.com/download>, accept Afreen's invite, and sign in.

```bash
tailscale status
```

Afreen's laptop should be listed.

### B2. Switch Console: the actual first-run screens

Download the **[Windows x64 installer directly](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-x64.exe)**
(`switch-console-x64.exe`), run it, then open **Switch Console** from Start.
For other systems use the direct [macOS Apple Silicon `.dmg`](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-arm64.dmg),
[macOS Intel `.dmg`](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-x64.dmg),
[Linux x64 `.deb`](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-amd64.deb), or
[Linux x64 AppImage](https://github.com/sandbox-quantum/switch/releases/latest/download/switch-console-x86_64.AppImage).
These installer URLs are listed in the [official Switch README](https://github.com/sandbox-quantum/switch/blob/main/README.md).
Do **not** download a `switch-agent-controller` dev `.tgz`: its release notes say
it is not for manual installation.

1. On **How do you want to run Switch?**, select **Join an existing server** on
   the right, then **Continue**. Afreen already runs the shared server in Docker.
   **On this computer** would start another server.
2. When asked for the server address, enter `http://<100.x.y.z>:8000`, using
   Afreen's Tailscale IP. The next screen should say **Sign in to
   <100.x.y.z>:8000**. On the current Console version, this screen asks for one
   address; do not enter the Gateway port `3000` in its place.
3. **Afreen:** sign in using `GATEWAY_ADMIN_EMAIL` and
   `GATEWAY_ADMIN_PASSWORD` from the local `switch-826/.env`. **Abhishek and
   Akshay:** use your own Switch account on this server. Afreen must create or
   invite it in the server's **Full admin interface → Users** if you have no
   account yet. Tailscale credentials are separate. Never send passwords in
   the group chat or screenshots.
4. If onboarding says **We can't find any of your workspaces**, choose
   **Skip** or **Finish later**. On our current setup this led to **Home** with
   the server marked **Connected**. Do not create another server or workspace
   just to clear this screen.
5. On **Home**, check the green **Connected** indicator. Click **Your Rooms**.
   The current server should show `#hermit-den` under Mattermost and
   `hermit-ledger` under **No messaging app**, both with three keeper agents.
   **Your Agents: 0** on Afreen's account means no coding agent is owned by
   that Console account yet; it does not erase those keeper registrations.
6. The current Console may show **Could not load Switch Trust settings (HTTP
   404)**. The basic server connection and rooms still worked when this
   appeared. Record it if it blocks another feature, but continue with the
   keeper and room checks.
7. **Link your messaging account** if you will use Mattermost: Home →
   Messaging apps → Mattermost → **Link** → find yourself → **This is me**.
   This associates your Mattermost identity with your Switch account.

Switch Console is a setup and inspection app. The shared server stays in
Docker on Afreen's laptop, and each person's keeper must run on that person's
laptop for presence. Keeping Console open is optional.

### B3. Your brain: onboard `hermit-<you>`

Settings → **Agent providers**: your provider must read **Installed**.

| You | Provider | Fallback |
|---|---|---|
| Afreen | Claude Code | OpenCode, Codex |
| Abhishek | OpenCode | Claude Code |
| Akshay | Codex | Claude Code |

Then **Your Agents → +**:

| Field | Set it to | Why |
|---|---|---|
| Run location | this computer | the brain runs on your laptop |
| Agent provider | yours, from the table | different brains is the demo |
| Working directory | `~/HermitWindow` (create it first) | **the only folder Hermit's brain can see**, so Switch enforces our privacy promise |
| Name | `hermit-<you>`, e.g. `hermit-abhishek` | must match `brain_agent` in your `hermit.config.toml` |
| Description | `Hermit's brain on <you>'s laptop` | required |
| **Who can talk to your agent** | **Anyone** | ⚠ the default, *Only me*, makes the brain refuse cues from `keeper-<you>` and messages from friends in the den. Hermit would go silent |
| Auto mode | on (default) | |
| Bypass permissions | **off** | |
| Advanced configuration | leave alone | |

Put the Hermit instructions where the brain reads them. In `~/HermitWindow`, Claude
Code reads `CLAUDE.md`, and Codex and OpenCode read `AGENTS.md`. Copy
`switch/knowledge/stage-directions.md` into that file. It tells the brain how to
answer `HERMIT-CUE/1` lines and when to call `assume_role("soul")`.

### B4. The keeper

```bash
python scripts/hermit_setup.py <you>
```

It writes `hermit.config.toml` for you (area-level location only), creates
`~/HermitWindow`, and checks Tailscale, the server, your provider CLI and your
token. Fix anything it marks ✗.

Set your keeper's key **in your shell only**:

```powershell
$env:HERMIT_SWITCH_TOKEN = "<your keeper api_key>"     # Windows PowerShell
```

```bash
export HERMIT_SWITCH_TOKEN=<your keeper api_key>       # macOS / Linux
```

---

## Part C — the rooms and the soul (Afreen, once everyone is connected)

1. **For a fresh server only, create `hermit-den`.** In Switch Console: Your Rooms → Create room → Mattermost.
   Paste `switch/rules/hermit-house-rules.md` into its **Instructions**.
2. **For a fresh server only, create `hermit-ledger`** as a room without a messaging app. Instructions: *"Machine log. Keepers write
   `HERMIT/1` lines here. Brains reply only with `HERMIT-ACK/1` lines."*
3. **Invite every agent into both rooms.** Type this in each room:

   ```text
   !invite-agent @hermit-afreen
   ```

   Repeat for `hermit-abhishek`, `hermit-akshay`, `keeper-afreen`, `keeper-abhishek`
   and `keeper-akshay`.
4. **Define the soul.** In `hermit-den`, ask Afreen's brain in plain words:

   > @hermit-afreen define an exclusive role in this room called `soul`, with the
   > instructions in `switch/rules/hermit-identity.md`. Then release any role you hold.

   `python switch/scripts/bootstrap_rooms.py --dry-run` prints the exact
   `define_role` call it should make.
5. **Check it in the den.** `!roles` must list `soul`, exclusive, with no holder yet.
6. **Record the room ids** for the keepers' config. They show on the room's page in
   Switch Console, or via `!room-url`.

---

## Part D — prove it before the real test

Do these in the den, in order. Each one is a gate for the next.

| # | Do | Pass when |
|---|---|---|
| D1 | From each laptop: `curl http://<100.x.y.z>:8000/health` | all three return 200 |
| D2 | `!list-agents` in both rooms | all six agents listed |
| D3 | `!agents-status` | each brain shows connected (address one to start it) |
| D4 | Ask `@hermit-afreen` to `assume_role("soul")` | `!roles` shows `soul` held by `hermit-afreen` |
| D5 | Ask `@hermit-akshay` to `assume_role("soul")` while Afreen holds it | **Switch refuses it.** That is the one-soul invariant, enforced by Switch |
| D6 | Type `@soul hi` | **whichever brain holds the soul answers.** That's the demo line: you talk to Hermit, not to a laptop |
| D7 | Afreen's brain releases, Akshay's claims | `!roles` follows the change |
| D8 | Kill the holder's session (close its terminal, or `!interrupt` and quit Console) and time how long until `!roles` shows no holder | **the real lease-expiry number.** Write it into `lease_expiry_s` and the README |

D5 and D8 are the two numbers the judges care about. Screen-record both.

---

## When something is wrong

| Symptom | Fix |
|---|---|
| `curl` times out from a laptop | `tailscale status` on both ends; is `SWITCH_BIND_ADDR` set to Afreen's Tailscale IP, and was the stack recreated? Check Windows firewall on Afreen's laptop. |
| Console says reachable but not signed in | a different problem: re-enter the account on that server |
| Brain ignores the keeper or friends | "Who can talk to your agent" is still *Only me*. Set it to **Anyone** |
| Brain replies "no session" | address it once so Console starts one, or run what `!run-cmd @hermit-<you>` prints |
| Your own message reads as a stranger's | link your Mattermost account in Console (B2 step 2) |
| Everything stops at once | Afreen's laptop slept, so check A1 |
