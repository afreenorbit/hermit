/**
 * Fake keeper API + SSE stream, so the critter can be built before the keeper
 * exists. Owner: C.  `pnpm --filter @hermit/critter mock`
 *
 * Must match shared/schemas/keeper-api.openapi.yaml.
 */
export {};
// TODO(C): node:http server on 47800 — /v1/health, /v1/status, /v1/events, /v1/shell
