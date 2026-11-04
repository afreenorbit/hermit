#!/usr/bin/env node
/**
 * Turn a simulator run into a committed, honestly-labelled demo journey.
 *
 *   python -m sim run sim/scenarios/three_cities_day.yaml
 *   node map/scripts/build-demo-journey.mjs three_cities_day
 *     → map/public/data/journey.three_cities.json
 *
 * Reads `sim/out/<scenario>/journey.json` and writes it back out with:
 *   - `source: { kind: "simulation", scenario }` so the page shows a
 *     SIMULATION badge (plan.md §9.2). This is the whole point of the script.
 *   - repeated shell pieces dropped (the shell is a set of ids),
 *   - each stop linked to the piece its completed favor grew, and that favor
 *     marked `done` (the piece carries `favor_id`; older exports left the stop
 *     pointing at nothing and the status at `open`),
 *   - `stats.favors_done` recounted from the unique completed favors.
 * Nothing is invented: every stop, time, favor and piece comes from the run.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');

const scenario = process.argv[2] ?? 'three_cities_day';
const outName = process.argv[3] ?? `journey.${scenario.replace(/_day$/, '')}.json`;
const src = resolve(repo, 'sim/out', scenario, 'journey.json');
const dst = resolve(repo, 'map/public/data', outName);

const j = JSON.parse(readFileSync(src, 'utf8'));

const seen = new Set();
j.shell = j.shell.filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));

const byFavor = new Map(j.shell.filter((p) => p.favor_id).map((p) => [p.favor_id, p]));
const done = new Set();
const linked = new Set();
for (const s of [...j.stops].sort((a, b) => a.seq - b.seq)) {
  const r = s.favor_received;
  const piece = r?.id ? byFavor.get(r.id) : undefined;
  if (!piece || linked.has(piece.id) || r.status === 'expired') continue;
  linked.add(piece.id);
  s.shell_piece_id ??= piece.id;
  r.status = 'done';
  done.add(r.id);
  // A piece is made while the favor's doer is hosting; the simulator stamps
  // every piece with the end of the run instead.
  if (
    piece.created_at === j.generated_at.replace('+00:00', 'Z') ||
    piece.created_at === j.generated_at
  )
    piece.created_at = s.left_at ?? s.arrived_at;
}
for (const s of j.stops)
  if (s.favor_left?.id && done.has(s.favor_left.id)) s.favor_left.status = 'done';

j.stats = { ...j.stats, favors_done: done.size };

const { v, generated_at, ...rest } = j;
const out = {
  v,
  generated_at,
  source: {
    kind: 'simulation',
    scenario,
    note: `python -m sim run sim/scenarios/${scenario}.yaml, then map/scripts/build-demo-journey.mjs`,
  },
  ...rest,
};
writeFileSync(dst, `${JSON.stringify(out, null, 2)}\n`);
console.log(
  `${dst}\n  ${out.stops.length} stops, ${out.shell.length} shell pieces, ${done.size} favors done — labelled SIMULATION`,
);
