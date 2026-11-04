/**
 * The preload bridge, with harmless fallbacks so both windows also run in a
 * plain browser (`pnpm --filter @hermit/critter dev:web`) for design work.
 * Owner: C.
 */
import type { HermitBridge } from '../../preload';

declare global {
  interface Window {
    hermit?: HermitBridge;
  }
}

const query =
  typeof location === 'undefined' ? new URLSearchParams() : new URLSearchParams(location.search);
const noop = (): void => undefined;

export const inElectron = typeof window !== 'undefined' && !!window.hermit;

export const bridge: HermitBridge = (typeof window !== 'undefined' && window.hermit) || {
  keeperUrl: query.get('keeper') ?? 'http://127.0.0.1:47800',
  chatUrl: query.get('chat'),
  setMouseOver: noop,
  setVisible: noop,
  dragStart: noop,
  dragEnd: noop,
  panel: (open: boolean) => {
    if (open) window.open('../panel/index.html', 'hermit-panel', 'width=360,height=520');
    else window.close();
  },
  setConnected: noop,
  soundState: noop,
  openExternal: (url: string) => void window.open(url, '_blank', 'noopener'),
  on: () => noop,
};
