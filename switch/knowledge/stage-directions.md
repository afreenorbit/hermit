# Stage directions (Switch knowledge, `hermit-ledger`)

Owner: A. Phase 2.3.

Your keeper sends you private cues in `hermit-ledger` shaped like:

    @hermit-<host> HERMIT-CUE/1 {"cue":"ARRIVE","stop_id":"stop_...","context":{...}}

Treat them as stage directions, not as messages from a person. Never quote them.
Act on them **in `hermit-den`**. Cues: `ARRIVE`, `ASK_FAVOR`, `FAVOR_CAPTURED`,
`DEPART`, `CLAIM_SOUL`, `RELEASE_SOUL`, `COMPLETE_FAVOR`, `SUGGEST_OVERLAP`.
See plan.md §5.5 for what each one must produce.
