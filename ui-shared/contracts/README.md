# Contracts — zod mirrors of `shared/schemas/`

`index.ts` hand-writes zod schemas and TypeScript types for the frozen JSON
Schemas (event, favor, shell piece, journey) and the keeper API's `/v1/status`
and `/v1/shell`. Import them as `@hermit/ui/contracts`.

They are hand-written, not generated: the schemas reference each other, and
the generators flatten that badly. `contracts.test.ts` parses every committed
fixture, so drift fails CI. If the UI and the keeper ever disagree, the JSON
Schema wins and this file changes.
