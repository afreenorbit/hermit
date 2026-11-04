# Actual test — Afreen, Abhishek, Akshay

Use this runbook for the three-laptop live test. The local simulation can rehearse the screens today. A real three-laptop pass requires the integration gates in Steps 1 and 2.

## Current checkpoint

- The real `switch-v0.9.0` server has `hermit-den` and `hermit-ledger`. A ledger line was posted by one registered keeper agent and received by another through `/agents/{id}/events`. The [Switch findings](switch-facts.md) record the verified API details.
- `SwitchRoomClient` implements that event polling, but `hermit-keeper run` still constructs fake room, lease and brain objects. Changing `lease_strategy` currently exits. The real client has not passed an end-to-end keeper test.
- The exclusive `soul` role and agent-directed claim/release are still an integration gate. `AgentInstructedLease.holder()` calls a role endpoint absent from the live HTTP API.
- A shared fake-lease simulation can run three keeper APIs on one computer. It proves screen transitions and state rules, but does not prove networking, real role exclusivity or laptop sleep recovery.
- The dashboard's local live view must be checked against `/v1/group/status` on the running version. A public static map cannot read a laptop's loopback API.

## Step 1 — finish real Switch room integration (Afreen)

1. On the Switch host, start the released stack from the sibling `switch-826` checkout. Run `docker compose -f deploy/local/standalone-v0.9.0.yml --profile collab --profile gateway --project-directory . up -d`. Check `docker compose ... ps` and `http://127.0.0.1:8000/health`.
2. Confirm the three keeper registrations, their individual agent UUIDs and API keys, and both room UUIDs. Store each key privately on its own host. Registration uses the shared registration token only for `POST /agents`; later calls use that agent's own API key. Never put keys in this runbook, screenshots or git.
3. Exercise `SwitchRoomClient` against the live server. Post `HERMIT/1` to the ledger with one agent, drain `/agents/{id}/events` with another, and confirm the decoded line and event ID. Only one component per keeper may drain that agent's event queue.
4. Wire the real room client into `hermit-keeper run`, with server URL, agent UUID, room UUIDs and API key from config/environment. Make a network failure visible as offline/unknown. Do not silently fall back to fake mode.
5. Repeat the post/read test through the normal keeper entry point. Stop Switch temporarily and verify the keeper reports loss of connection. Restore Switch and verify recovery.

**Gate:** Step 1 is done only when two separate keeper processes exchange a real ledger event through Switch and recover after a server interruption. The earlier API probe alone is not enough.

## Step 2 — finish exclusive soul integration (Afreen, then all three)

1. Create the `soul` role in `hermit-den` with the room rules. Use `python switch/scripts/bootstrap_rooms.py --dry-run` to inspect the intended operations. The script's live execution is currently unfinished, so apply them through a connected Switch agent.
2. Connect Afreen's brain to Switch. Have it call `assume_role("soul")`, then release it. Confirm its role instructions and write claim/release events to the ledger.
3. Replace the unavailable HTTP role-holder lookup in `AgentInstructedLease` with a tested authority strategy. Ledger observation must handle stale claims and a brain dying without a release line. Do not allow two keepers to report Visiting based solely on optimistic ACKs.
4. Connect Abhishek's and Akshay's brains. Race two claims ten times. Switch must reject the second every time. Kill a holder's session, measure actual lease expiry and prove another brain can claim afterward.
5. Wire `lease_strategy = "agent_instructed"` into the normal CLI runtime. Run the Python suite, simulation suite and one live two-keeper handoff before expanding to three laptops.

**Gate:** exactly one brain holds the real Switch role at a time, and all keeper status responses converge on the same holder, including after abrupt loss.

## Step 3 — put Switch on a reachable, awake host (Afreen)

Use an always-on computer or VPS. If Afreen's laptop hosts Switch and sleeps, the test stops for everyone.

1. Create one Tailscale tailnet and invite Abhishek and Akshay with their own accounts. Install Tailscale on the Switch host and all three laptops. Sign in, connect, and approve devices as needed.
2. On the Switch host, run `tailscale ip -4`. Record its `100.x.y.z` address. In `switch-826/.env`, set `SWITCH_BIND_ADDR=0.0.0.0`, then recreate the compose services. Do not open router ports. Keep access limited to the tailnet.
3. From each laptop, run `tailscale status` and `curl http://100.x.y.z:8000/health`. Each must receive a healthy response. Also open Mattermost at `http://100.x.y.z:8065` if using it for conversation.
4. Verify that the server remains reachable while one participant closes their laptop. If the Switch host itself sleeps, move the stack before the test.

Record the actual Tailscale IP privately. It can change if the server machine is replaced.

## Step 4 — prepare each laptop (everyone)

| Person | `host_id` | Intended brain | Responsibility |
|---|---|---|---|
| Afreen | `afreen` | Claude Code | Switch host, ledger, timing and logs |
| Abhishek | `abhishek` | OpenCode | Favor flow, independent status observations |
| Akshay | `akshay` | Codex | Three critter screens, dashboard and recordings |

1. Pull the agreed integration commit and install Python 3.11+, Node 20+, Docker only on the Switch host, and Tailscale. On Windows PowerShell, create a venv with `py -m venv .venv`, activate with `.\.venv\Scripts\Activate.ps1`, then run `pip install -e "keeper[dev]"`.
2. Copy `hermit.config.example.toml` to ignored `hermit.config.toml`. Set your unique host ID, area-level city coordinates, timezone `Asia/Kolkata`, brain provider, Switch Tailscale URL and the verified real lease strategy. Put your own agent UUID and room UUIDs wherever Step 1's integration specifies. Set `HERMIT_SWITCH_TOKEN` in your own shell to your own agent API key.
3. Run `python -m hermit_keeper check --switch`, then `python -m hermit_keeper run`. In another terminal run `python -m hermit_keeper status` and open `http://127.0.0.1:47800/v1/group/status`. Confirm all three hosts appear after every keeper starts.
4. Start the desktop companion using the UI integration branch's documented command, normally `pnpm --filter @hermit/critter dev`. On Windows without pnpm on PATH, use Corepack or the project-local executable. Verify the companion stays visible on all three laptops with distinct Visiting/Waiting/Sleeping/Offline states.
5. Optionally run `pnpm dev:map`. Read Vite's printed port, usually 5173. Open the local page with its live keeper query parameter as documented by the integrated UI. The dashboard may stay open for observation, but the critter must work when it is closed.

Everyone may join the Mattermost den to send messages, but no one needs to leave its page open to provide presence. The keeper reads local activity. Confirm the brain responds to a den message before recording that scenario. Discord requires its bridge to be configured and tested separately.

## Step 5 — run the three-laptop scenarios (everyone)

For each row, note wall-clock time, the holder from each keeper's status, all three mascot moods, the dashboard state, ledger event IDs, and any delay. Akshay records screens, Afreen records server/keeper logs, Abhishek checks favor delivery.

| Test | Action | Expected observation |
|---|---|---|
| Initial state | All three type, wait through the arrival debounce | One Visiting, two Waiting. All status views name the same holder. |
| Akshay → Afreen | Akshay hosts, then goes idle beyond the configured threshold and minimum dwell. Afreen works; Abhishek stays active. | Akshay Away then Sleeping; Afreen Arriving then Visiting; Abhishek Waiting. Only one holder at each point. |
| Conversation | Abhishek posts in the den while Afreen hosts. | The active host's brain responds. Ledger/den history identifies the speaker correctly. |
| Manual departure | Current host invokes `python -m hermit_keeper depart`. | Away precedes release, then another active host arrives. |
| Lid close | Close the hosting laptop without departing. | After measured lease expiry, the next active host claims; previous stop is recorded as abrupt. |
| Everyone idle | Stop interaction on all three until thresholds pass. | No Visiting state and no invented activity. First returning user becomes eligible after debounce. |
| Keeper stopped | Stop one keeper, then restart it. | Its critter shows Offline and later recovers. Other keepers remain consistent. |
| Network interruption | Disconnect one host's Tailscale/Wi-Fi, then reconnect. | Unknown/offline is shown where state cannot be verified. No second Visiting state appears. |
| Bedtime | Set one host's bedtime to the present during a test config run. | It leaves and remains locked out until bedtime ends. |
| Favor | Leave, assign and complete a favor across a handoff. | Correct recipient sees it, completion persists, and the shell/journey reflects it. |

Use `python -m hermit_keeper override awake`, `override asleep`, and `override auto` to rehearse transitions quickly. Record override-driven results as simulations of presence. Repeat the key handoff with actual idle time for the real result.

## Pass criteria and fallback

Pass only if the real role never has two holders, all three keeper status views agree, each critter shows the appropriate local state, an abrupt loss recovers, and the favor/ledger survives across hosts. Report the measured times and any failed case honestly.

If Steps 1 or 2 are unfinished tomorrow, run `python -m sim live` on one computer and test the three local ports (47801–47803). Label the recording **simulation**. A static hosted dashboard can display the exported journey, while live group status requires a reachable backend designed for remote readers.
