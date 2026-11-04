# Switch facts — answers to every ⚠ VERIFY

Owner: Afreen. Phase 0. **Every claim here is cited to a file in the Switch
source**, not inferred from docs or guessed from behaviour.

Source read: `afreenorbit/switch` @ `90c65aae` (local checkout at
`Desktop/Afreen/switch-826`). Re-check these if you move to a different Switch
version before the pilot.

---

## SP1 — Can a role be exclusive, and is there a lease?

**Yes, and the lease is exactly what Hermit needs.**

Roles are room-scoped, assumable instruction bundles. `define_role(name,
instructions, exclusive=True)` creates one; `create_room(roles=[...])` can
define them at creation, so bootstrap is one call.

> "exclusive roles allow at most one live holder"
> — `core/switch_core/bridges/agent/operations/definitions.py:969`

**The soul is a real Switch primitive.** We are not simulating exclusivity.

---

## SP2 — Can the keeper claim/release the role on the brain's behalf?

**No. And that is the single most important finding in this document.**

`assume_role` / `release_role` are *agent operations*, resolved from the
caller's live connection:

> "`assume_role` — resolves it from the connection rather than from an MCP
> [argument]" — `core/switch_core/bridges/agent/api/operations.py:113`

There is no HTTP, gateway or console path that assumes a role for someone else
(searched `gateway/` and `console/src` — nothing). The lease belongs to the
**session that called it**:

> "this acquires a lease held by you specifically: while your session stays
> alive the seat is yours, and it auto-releases shortly after you disconnect so
> another agent can take over. **A sibling session of the same agent cannot hold
> it open on your behalf.**" — `definitions.py:1131`

### What this changes

`lease_strategy = "gateway"` (plan §5.2, option G) **does not exist** and must
not be built. The strategy is `agent_instructed`: the keeper cues the brain over
the ledger, and the brain calls `assume_role("soul")` itself.

### Why this is better, not a consolation prize

`assume_role` returns `{"role", "instructions"}` — the role's instruction delta.
So the agent that holds the soul **receives Hermit's identity as its
instructions, from the room**. Hermit's personality is not in our code or in our
prompt; it is in a Switch room role, handed to whichever agent currently holds
it. That is a much stronger answer to "would this project stop working without
Switch?" than a keeper poking an API would have been.

**Note for the README and the video:** the soul is held by the *brain* (the
friend's own Claude Code / OpenCode / Codex), not by our keeper. One sentence,
and it is the most Switch-native thing in the project.

---

## SP3 — What happens when the lid closes?

**The lease auto-releases shortly after the holding session disconnects.** We do
not have to detect this ourselves, and no keeper needs to be alive for it.

Liveness follows the *session*, not the agent — this was a deliberate fix:

> "A lease has always been kept alive by either its own heartbeat or the agent
> having some live connection. The second test is agent-wide, so once an agent
> holds one permanent controller connection it is always true and no lease would
> ever expire. **Naming the holding session is what lets liveness follow the
> holder instead of the agent.**"
> — `migrations/versions/b5e19d073c4a_role_lease_owning_session.py`

So: lid closes → the brain's session dies → the soul frees → the next awake
friend's brain can take it. F1 and the abrupt-departure path are native
behaviour, not something we built.

⚠ **Still to measure:** how long "shortly after" actually is. Put the real
number in `expiry_delay_s` and report it honestly in the README. Until measured,
`FakeSoulLease` uses 8 s, which is a guess.

Relevant endpoints exist for keeping a lease alive deliberately:
`POST /{agent_id}/leases/renew`, `/connection/renew`, `/watch/heartbeat`
(`bridges/agent/api/handlers.py:599-645`).

---

## SP4 — How does the keeper watch who holds the soul?

`list_roles()` returns, per role, `held_by` — the live holders:

> "Each holder is an object `{"name", "present_here", "session_room"}`:
> `present_here` is True when that holder's assuming session is connected to
> THIS room right now; otherwise `session_room` names the room its session is
> currently attending (a lease survives room hops), or is null if no bound
> session can be located." — `definitions.py:1041`

That is our `SoulLease.holder()`. It also gives us something the fake does not:
we can tell a holder who is *present in the den* from one whose session wandered
off, which is a better "is Hermit really here?" signal than our own bookkeeping.

`assume_role` also "fails if you already hold a role (release it first)" — one
role per agent, so the brain must release before anything else.

---

## SP5 — Are favors Switch room Tasks?

**No. Do not build this.** (plan §2.3 F3 and §5.6 both assume Tasks.)

A `Task` row exists (`db/models.py:1294`) but it is **agent-to-agent
delegation**, not a note for whoever turns up next:

- `requester_agent_id` and `performer_agent_id` are both `nullable=False`
- it carries `accepted_at` / `finalised_at` / `outcome` — a work item
- **no agent operation exposes tasks at all** (searched `operations/definitions.py`)

A favor has no performer when it is written. That is the entire point: you leave
it for whoever Hermit visits next, and nobody knows who that is yet.

### Use room documents instead

`create_room_document(name, description, instructions, content)` →
`{"document_id"}`. Room-scoped, visible to all participants, readable by others
with `load_internal_documents`, updatable by the creating agent
(`definitions.py:555`).

**Recommended shape** (Abhishek, Phase 4.1):

- The **ledger** stays the source of truth for favor state — `FAVOR_LEFT`,
  `FAVOR_ASSIGNED`, `FAVOR_COMPLETED` are already in `event.schema.json` and
  `export_journey.py` already reads them. Nothing changes there.
- The **visible artifact** in the den is a room document, one per favor, named
  `favor-<ulid>`. That is what a friend sees and what Hermit reads on arrival.
- `favor.schema.json`'s `switch_task_id` becomes `switch_document_id`. One
  field rename, and the contract change needs two approvals.

Only the creating agent can update a document, so "mark it done" is a ledger
event plus a new document revision by the same brain — not a cross-agent write.

---

## SP6 — Can the keeper be an agent?

Yes. `bridges/agent/api/handlers.py` exposes registration (`POST ""`,
`/register-known`, `/register-known-bulk`), messaging (`/{agent_id}/message`),
typing, status, and the renewal endpoints above.

But note SP2: **the keeper must not take the soul.** If the keeper assumed the
role, the brain could not (exclusive, one holder) and Hermit would have no
voice. The keeper is a room member that writes the ledger and cues the brain.

---

## What changes in the plan

| Plan says | Reality | Action |
|---|---|---|
| `lease_strategy = "gateway"` default | No external role assumption exists | Default is `agent_instructed`; delete `lease/gateway.py` |
| `lease/task_lock.py` fallback | Tasks are not agent-accessible | Delete; the real fallback is "the brain retries" |
| Favors are room Tasks | Tasks need a performer up front | Favors are room documents + ledger events |
| `favor.switch_task_id` | — | Rename to `switch_document_id` |
| Keeper claims the soul | Only the holding session can | Keeper cues; brain assumes |

## Still open

- [ ] Measure real lease-expiry latency after a disconnect → `expiry_delay_s`.
- [ ] Confirm the agent-protocol handshake end to end with a live server.
- [ ] Confirm Discord bridge setup (`list_bridges` exists; not yet exercised).
