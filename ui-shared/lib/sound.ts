/**
 * Four chiptune blips, synthesised with WebAudio — no audio files to ship.
 * Muted by default; the preference lives in localStorage (wrapped in try/catch,
 * because storage can be blocked). Owner: C. plan.md §3.6.
 */

export type SoundName = 'arrive' | 'leave' | 'quest' | 'shell';

const KEY = 'hermit.sound';

type Note = {
  f: number;
  to?: number;
  at: number;
  dur: number;
  type?: OscillatorType;
  vol?: number;
};

const SOUNDS: Record<SoundName, Note[]> = {
  arrive: [{ f: 330, to: 880, at: 0, dur: 0.18, type: 'square' }],
  leave: [{ f: 880, to: 220, at: 0, dur: 0.22, type: 'square' }],
  quest: [
    { f: 784, at: 0, dur: 0.1, type: 'triangle', vol: 0.5 },
    { f: 1175, at: 0.11, dur: 0.18, type: 'triangle', vol: 0.5 },
  ],
  shell: [523, 659, 784, 1047, 1319].map((f, i) => ({
    f,
    at: i * 0.06,
    dur: 0.09,
    type: 'square' as const,
    vol: 0.35,
  })),
};

let ctx: AudioContext | null = null;
const listeners = new Set<(on: boolean) => void>();

function read(): boolean {
  try {
    return globalThis.localStorage?.getItem(KEY) === 'on';
  } catch {
    return false;
  }
}

let enabled = read();

export const sound = {
  isEnabled(): boolean {
    return enabled;
  },
  setEnabled(on: boolean): void {
    enabled = on;
    try {
      globalThis.localStorage?.setItem(KEY, on ? 'on' : 'off');
    } catch {
      /* storage blocked: keep it in memory */
    }
    listeners.forEach((l) => l(on));
    if (on) this.play('quest');
  },
  subscribe(listener: (on: boolean) => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },
  play(name: SoundName): void {
    if (!enabled || typeof window === 'undefined') return;
    try {
      const Ctor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return;
      ctx ??= new Ctor();
      const now = ctx.currentTime + 0.01;
      for (const n of SOUNDS[name]) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = n.type ?? 'square';
        osc.frequency.setValueAtTime(n.f, now + n.at);
        if (n.to) osc.frequency.exponentialRampToValueAtTime(n.to, now + n.at + n.dur);
        const vol = 0.08 * (n.vol ?? 1);
        gain.gain.setValueAtTime(vol, now + n.at);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + n.at + n.dur);
        osc.connect(gain).connect(ctx.destination);
        osc.start(now + n.at);
        osc.stop(now + n.at + n.dur + 0.02);
      }
    } catch {
      /* audio is decoration; never let it break the page */
    }
  },
};
