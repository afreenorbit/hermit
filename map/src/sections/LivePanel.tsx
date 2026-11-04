/**
 * Who has Hermit right now — the dashboard anyone in the group can leave open.
 *
 * This is the only live thing on the page. Everything else is the exported
 * journey, which is history; this panel says so out loud so nobody reads a
 * static file as a feed.
 *
 * The desktop critter does not need this page. It talks to its own keeper
 * directly, and works with the browser closed.
 */
import { PixelBox, PocketHermit, moodLine } from '@hermit/ui';

import { secondsSince, type Group, type GroupHost } from '../hooks/useGroup';

interface Props {
  group: Group | null;
  error: string | null;
  keeper: string | null;
}

export function LivePanel({ group, error, keeper }: Props) {
  if (!keeper) {
    return (
      <PixelBox as="section" tab="Right now" className="panel live" id="live">
        <p className="live__off">
          Live status is off. Start a keeper and open this page with{' '}
          <code>?live=http://127.0.0.1:47801</code> to see who has Hermit.
        </p>
      </PixelBox>
    );
  }

  const hosts = group?.hosts ?? [];
  const holder = group?.soul_holder ?? null;
  const unreachable = !!error;

  return (
    <PixelBox as="section" tab="Right now" className="panel live" id="live">
      <header className="live__head">
        <p className="live__lede">
          {unreachable
            ? 'Cannot reach the keeper — this is the last thing it told us.'
            : holder
              ? `Hermit is with ${titleCase(holder)}.`
              : hosts.length
                ? 'Hermit is between friends.'
                : 'No laptops have checked in yet.'}
        </p>
        <span className={`live__dot${unreachable ? ' live__dot--bad' : ''}`} aria-hidden />
        <span className="live__meta">
          {unreachable ? 'stale' : 'live'} · {keeper.replace(/^https?:\/\//, '')}
        </span>
      </header>

      <ul className="live__hosts">
        {hosts.map((host) => (
          <HostRow key={host.host_id} host={host} holder={holder} />
        ))}
      </ul>

      {hosts.length === 0 && !unreachable && (
        <p className="live__off">Waiting for the first heartbeat…</p>
      )}

      <p className="live__note">
        Live. Everything else on this page is the exported journey — history, not a feed.
      </p>
    </PixelBox>
  );
}

function HostRow({ host, holder }: { host: GroupHost; holder: string | null }) {
  const ago = secondsSince(host.last_seen);
  return (
    <li className={`live__host live__host--${host.mood}`}>
      <PocketHermit mood={host.mood} size={56} still label="" />
      <div className="live__host-text">
        <strong>{titleCase(host.host_id)}</strong>
        {/* The line is written from this laptop's point of view, so it needs
            the group's holder, not this row's own id. */}
        <span>{moodLine(host.mood, holder, host.host_id)}</span>
        <small>
          {host.stale
            ? ago == null
              ? 'never checked in'
              : `last seen ${formatAgo(ago)} ago`
            : host.present === false
              ? 'away from the keyboard'
              : 'at the keyboard'}
        </small>
      </div>
      {host.holding && <span className="live__badge">has Hermit</span>}
    </li>
  );
}

function formatAgo(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
