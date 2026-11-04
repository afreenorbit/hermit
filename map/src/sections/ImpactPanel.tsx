/** The "why it matters" panel: favors, friends reached, chains. Owner: C. plan.md §7.3. */
import { formatHandoffMs, PixelBox, StatTile } from '@hermit/ui';
import type { JourneyT } from '@hermit/ui/contracts';

import type { Derived } from '../lib/derive';
import { FriendshipWeb } from './FriendshipWeb';

export function ImpactPanel({ journey, derived }: { journey: JourneyT; derived: Derived }) {
  const s = journey.stats;
  const favorsDone = s.favors_done ?? derived.favorsDone;
  const showCalls = s.overlaps_suggested != null && s.overlaps_suggested > 0;

  return (
    <PixelBox as="section" tab="Impact" className="panel panel--impact" aria-labelledby="impact-h">
      <h2 id="impact-h" className="hm-sr">
        What friends did for each other
      </h2>
      <div className="impact">
        <div className="stats">
          <StatTile
            label="Favors done"
            value={favorsDone}
            icon="heart"
            tone="ember"
            hint={`${s.favors_left ?? 0} left in all`}
          />
          <StatTile
            label="Friends reached"
            value={derived.friendsReached}
            icon="people"
            tone="leaf"
            hint="did at least one favor"
          />
          <StatTile
            label="Longest chain"
            value={derived.longestChain}
            icon="chain"
            tone="sun"
            hint="hops in a row with a favor done"
          />
          <StatTile
            label="Median handoff"
            value={s.median_handoff_ms ?? '—'}
            format={(n) => formatHandoffMs(n)}
            icon="clock"
            tone="sea"
            hint={`${s.handoffs ?? 0} handoffs`}
          />
          {showCalls && (
            <StatTile
              label="Calls found"
              value={s.overlaps_taken ?? 0}
              icon="chat"
              tone="dream"
              hint={`of ${s.overlaps_suggested} overlaps suggested`}
            />
          )}
        </div>
        <FriendshipWeb derived={derived} />
      </div>
    </PixelBox>
  );
}
