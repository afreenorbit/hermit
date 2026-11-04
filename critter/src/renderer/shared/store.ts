/**
 * useKeeperEvents — Zustand store over the keeper's SSE stream. Owner: C.
 * plan.md §6.1.
 *
 * SSE with reconnect backoff (1s → 10s), /v1/status on connect and every 30s
 * as a safety net, /v1/shell on connect; every payload zod-validated.
 */
import { sound } from '@hermit/ui';
import { Event, KeeperShell, KeeperStatus } from '@hermit/ui/contracts';
import { create } from 'zustand';

import { bridge } from './bridge';
import {
  applyEvent,
  applyStatus,
  finishArriving,
  finishLeaving,
  initial,
  type CritterState,
} from './reduce';

interface Actions {
  start: () => () => void;
  depart: () => Promise<void>;
  arrived: () => void;
  left: () => void;
}

export const useKeeper = create<CritterState & Actions>()((set, get) => {
  const base = bridge.keeperUrl.replace(/\/$/, '');

  const refreshStatus = async (): Promise<void> => {
    const res = await fetch(`${base}/v1/status`);
    const parsed = KeeperStatus.safeParse(await res.json());
    if (!parsed.success) throw new Error('bad /v1/status payload');
    set((s) => applyStatus(s, parsed.data));
  };

  const refreshShell = async (): Promise<void> => {
    const res = await fetch(`${base}/v1/shell`);
    const parsed = KeeperShell.safeParse(await res.json());
    if (parsed.success) set({ shell: parsed.data.pieces });
  };

  const disconnected = (): void => {
    set({ ...initial, shell: get().shell });
    bridge.setConnected(false);
  };

  return {
    ...initial,

    start: () => {
      let es: EventSource | null = null;
      let retry = 1000;
      let retryTimer = 0;
      let alive = true;

      const connect = (): void => {
        if (!alive) return;
        es = new EventSource(`${base}/v1/events`);
        es.onopen = () => {
          retry = 1000;
          bridge.setConnected(true);
          void Promise.all([refreshStatus(), refreshShell()]).catch(disconnected);
        };
        es.onmessage = (msg) => {
          let raw: unknown;
          try {
            raw = JSON.parse(msg.data as string);
          } catch {
            return;
          }
          const parsed = Event.safeParse(raw);
          if (!parsed.success) return;
          const before = get();
          set((s) => applyEvent(s, parsed.data));
          const after = get();
          if (after.phase === 'arriving' && before.phase !== 'arriving') sound.play('arrive');
          if (after.phase === 'leaving' && before.phase !== 'leaving') sound.play('leave');
          if (after.quest && !before.quest) sound.play('quest');
          if (after.celebrate > before.celebrate) sound.play('shell');
          // status carries Hermit's latest den line; cheap on localhost
          void refreshStatus().catch(() => undefined);
        };
        es.onerror = () => {
          es?.close();
          disconnected();
          window.clearTimeout(retryTimer);
          retryTimer = window.setTimeout(connect, retry);
          retry = Math.min(10_000, retry * 2);
        };
      };

      connect();
      const poll = window.setInterval(() => {
        if (get().connected) void refreshStatus().catch(() => undefined);
      }, 30_000);

      return () => {
        alive = false;
        es?.close();
        window.clearTimeout(retryTimer);
        window.clearInterval(poll);
      };
    },

    depart: async () => {
      const response = await fetch(`${base}/v1/depart`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ reason: 'manual' }),
      });
      if (!response.ok) throw new Error('Departure request failed');
    },

    arrived: () => set((s) => finishArriving(s)),
    left: () => set((s) => finishLeaving(s)),
  };
});
