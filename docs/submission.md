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
> A tiny visitor follows who's around, carries small favors between friends, and lets them leave notes through Switch.

**Repo:** https://github.com/afreenorbit/hermit

**Video:** [fill after recording]

**Description:**

> Friends rarely drift apart because they're far away. They drift because nobody starts the
> conversation. We're three friends in Bengaluru, 25 km apart, and we still go weeks without seeing
> each other.
>
> Hermit is a small creature with no home of its own. A keeper on each friend's laptop watches
> whether someone is at the keyboard. The desktop mascot shows the same shared holder on all
> screens. The host can leave a small favor for the next person; completing it grows a shared shell.
> A friend who is not hosting can send a note to whoever Hermit is visiting. The journey page
> records where it has been, clearly separating exported history from live presence.
>
> **Switch is the shared engine.** Each keeper is a custom Switch agent. Presence, holder claims,
> favors, notes and shell pieces go through the Switch ledger room. Without it, the live laptops
> cannot agree on the holder or carry a task to another friend. The current `keeper_claimed` mode
> coordinates a provisional holder through ledger order. An exclusive `soul` role for the friends'
> Codex, Claude Code and OpenCode agents is implemented as a separate mode but has not been proven
> with this live server; do not claim that exclusivity in the submission yet.
>
> **Built and tested.** The Python gate passed 266 keeper tests and nine time-compressed simulations;
> 104 UI unit tests passed. Afreen's keeper authenticated to real `switch-v0.9.0`, claimed and released
> a provisional holder, and wrote a real favor to the ledger. The full cross-laptop completion path
> is automated-tested using separate keeper books and a fake shared room. A measured three-laptop
> AI role handoff and pilot results are still pending. The illustrated [blog](blog.md) labels every
> screenshot and simulation honestly.
>
> **Privacy by design.** The keeper sends only a count of files in the chosen window folder, never
> their names. Locations are area-level. The bedtime rule stops Hermit rewarding late-night work.
> The group's Switch server carries the shared data; the mascot API stays on each laptop's loopback.

**What we'd say if asked "does it work without Switch?"**
> The real multi-laptop experience stops. The keepers cannot agree on the holder or exchange favors,
> notes and shell pieces. The fake lease is for tests and labelled simulation only. The intended
> exclusive AI role depends on Switch too, but that live gate remains open.

---

## 2. #HowISwitch social post (draft)

Attach the handoff GIF: `docs/assets/route-replay.gif` is sample data, so caption it that way, or
use a real-run clip **[fill after the real run]**.

> We gave our friend group a pet that has no home.
>
> Hermit follows who's around, carries a small favor to the next friend, and grows a shared shell
> when they do it. A note can reach whoever it is visiting.
>
> Switch rooms carry the shared holder, favors, notes and shell. The exclusive AI role is our next
> live test; this clip shows the keeper mode and labelled simulation.
>
> #HowISwitch @WeMakeDevs [repo link]

(Keep it under 280 characters for X and trim the middle paragraph if needed.)

---

## 3. Best Blog entry

Use the finished illustrated [blog](blog.md). It includes the real local Switch
claim and favor, the Edge captures, a labelled sample journey, architecture,
reproduction steps and limits. Publish its text only after checking that the
linked images render at the chosen destination.

---

## 4. Pre-submit checklist

- [ ] Every **[fill after …]** above is filled with real evidence, or the sentence is deleted.
- [ ] README "Status" matches what actually happened.
- [ ] License chosen by the team and added (README currently says "to be decided"). Switch is
      Apache 2.0 + Commons Clause.
- [ ] Video uploaded and the link works while logged out.
- [ ] Repo public, no secrets in history (`git log -p | grep -i token`).
- [ ] Track 02 selected on the form.
