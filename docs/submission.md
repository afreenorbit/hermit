# Submission drafts

Owner: Akshay (story), reviewed by all three. Deadline: **Nov 7 2026, 21:00 IST**. Aim to submit by 18:00.

Anything marked **[fill after the real run]** or **[fill after the pilot]**
depends on evidence that does not exist yet. If that evidence never arrives,
delete the sentence. Do not soften it into a vaguer claim.

---

## 1. Form text

**Title:** Hermit

**Track:** Track 02: Best Personal or Creative Workflow

**One-liner (≤ 140 chars):**
> A tiny creature that lives on one friend's laptop at a time, speaks through their own AI agent, and moves to whoever's still around.

**Repo:** https://github.com/afreenorbit/hermit

**Video:** [fill after recording]

**Description:**

> Friends rarely drift apart because they're far away. They drift because nobody starts the
> conversation. We're three friends in Bengaluru, 25 km apart, and we still go weeks without seeing
> each other.
>
> Hermit is a small creature with no home of its own. It lives on one friend's laptop at a time
> and thinks with *that friend's* coding agent: Claude Code on one laptop, OpenCode on another,
> Codex on the third. When that friend goes quiet, Hermit moves to whoever is still around and
> carries a small favor from the last friend. Doing a favor grows Hermit's shell. Over a week,
> the group ends up with a journey map and a shell they built together.
>
> **Switch is the engine, not the transport.** Hermit's "soul" is an exclusive Switch role. Only
> one agent can hold it, so there is only ever one Hermit. The role's instructions *are* Hermit's
> personality, so whichever brain wins the soul becomes Hermit. When a laptop lid slams shut, the
> session-bound lease frees the soul and the next friend picks it up without anyone saying goodbye.
> The rooms are the group's only shared memory: a ledger room that every laptop's keeper folds into
> the same answer, and a den where friends talk to Hermit with `@soul`. Each laptop runs two agents
> in the same rooms: the friend's off-the-shelf coding agent, and our keeper, a custom Python
> agent.
>
> **Built and tested.** The keeper has a strict-typed state machine, Hypothesis property tests for
> the one-soul invariant, and more than 250 keeper tests in CI. Nine time-compressed scenarios (lid slam,
> bedtime, simultaneous wake, nobody awake and more) run in CI, and a judge can run them on one
> machine in about 10 minutes. The Switch client is verified against a real `switch-v0.9.0` server
> for registration, posting and receiving. The full handoff (claims, lid slam, outage, favors) is
> proven over real HTTP against a Switch stand-in, including 10 three-way claim races with exactly
> one winner every time. [fill after the real run: "and on three real laptops with real brains,
> where Switch refused the second claim N/N times and the lease freed in X s".]
>
> **Privacy by design.** The brain sees one folder you chose (Switch Console scopes it to
> `~/HermitWindow`), and the group only ever sees the file *count*. Locations are area-level,
> never addresses. There is a bedtime rule, so Hermit leaves when you should sleep and never
> rewards staying up. The extras are opt-in. There is no server of ours, only the group's own
> Switch.
>
> [fill after the pilot: one sentence with the pilot's real numbers, or delete.]

**What we'd say if asked "does it work without Switch?"**
> No. The offline mode exists for UI work and the simulator, and everything it produces is labelled
> SIMULATION. Without the exclusive role there is no single Hermit, without role instructions it
> has no portable identity, and without the session lease a closed laptop keeps the soul forever.

---

## 2. #HowISwitch social post (draft)

Attach the handoff GIF: `docs/assets/route-replay.gif` is sample data, so caption it that way, or
use a real-run clip **[fill after the real run]**.

> We gave our friend group a pet that has no home.
>
> Hermit lives on one of our laptops at a time and talks through *that* person's AI: Claude Code,
> OpenCode or Codex. When you go quiet, it moves to whoever's still around and brings a favor
> from the last friend.
>
> The trick: Hermit's soul is an exclusive Switch role. Only one agent can hold it, and its
> instructions ARE Hermit's personality. Close your laptop and the lease frees itself, and the
> next friend gets Hermit.
>
> #HowISwitch @WeMakeDevs [repo link]

(Keep it under 280 characters for X and trim the middle paragraph if needed.)

---

## 3. "Best Blog" post outline (optional)

**Working title:** *We made our AI agents share one soul*

1. **The problem, personally.** Three friends, 25 km apart, weeks without meeting. Group chats die
   because nobody starts them. Cite the two stats from the README.
2. **The idea.** A creature that has to *move* to stay alive, so someone always has a reason to say
   something.
3. **The Switch finding that changed the design.** We planned for our code to claim the role. Then
   we read the Switch source and found that only the agent itself can `assume_role`, and that the
   role's instructions come back to it. So the friend's own brain holds the soul, and Hermit's
   identity lives in the room. Quote switch-facts SP2.
4. **Three surprises from a real server.** No roles endpoint over HTTP, so the keepers fold the
   ledger to observe the holder. Room history came back empty, so we read a drain-once `/events`
   queue with exactly one poller. Favors can't be Tasks, because a Task needs a performer up front.
5. **Making "one Hermit" provable.** The ledger fold (ordering by the brain's ACK and the
   stale-holder rule), Hypothesis property tests, the stand-in server, and 10 three-way races.
   Be explicit about what the stand-in does and does not prove.
6. **The real run.** [fill after the real run: what D5 and D8 showed, the measured lease expiry,
   what broke.]
7. **The pilot.** [fill after the pilot: numbers, two quotes with permission, honest limits. If
   there was no pilot, say so.]
8. **Privacy as a feature.** The window folder (count, not names), area-level location, and the
   bedtime rule.
9. **What we'd do next.** For example: a measured lease-expiry setting per server, the Discord
   bridge, and `--from-room` export.

Every number in the post must come from `docs/pilot-results.md`, the real-run notes, or a command
whose output is pasted. Label any simulated number SIMULATION.

---

## 4. Pre-submit checklist

- [ ] Every **[fill after …]** above is filled with real evidence, or the sentence is deleted.
- [ ] README "Status" matches what actually happened.
- [ ] License chosen by the team and added (README currently says "to be decided"). Switch is
      Apache 2.0 + Commons Clause.
- [ ] Video uploaded and the link works while logged out.
- [ ] Repo public, no secrets in history (`git log -p | grep -i token`).
- [ ] Track 02 selected on the form.
