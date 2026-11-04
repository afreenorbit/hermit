/**
 * Tilli — Hermit's mascot, drawn as a layered SVG rig so every state from the
 * movement demo can be animated: arriving with a letter, visiting, curious,
 * talking, celebrating, sleeping tucked in the shell, and walking away.
 * Owner: C. Design: the Tilli character sheet (map/public/assets/tilli.jpeg).
 *
 * `tilliSvg()` returns a self-contained SVG string, so the same drawing is used
 * by the React component, the Electron critter and the postcard canvas.
 * Motion lives in styles/components.css (`.tilli--<mood>` classes); the eyes
 * follow `--tilli-look-x/y` CSS variables so tracking the cursor never
 * re-renders the markup.
 */

export type TilliMood =
  | 'happy'
  | 'arriving'
  | 'curious'
  | 'talking'
  | 'celebrate'
  | 'sleeping'
  | 'away'
  | 'walk'
  | 'wave';

export const TILLI_MOODS: readonly TilliMood[] = [
  'happy',
  'arriving',
  'curious',
  'talking',
  'celebrate',
  'sleeping',
  'away',
  'walk',
  'wave',
];

/** The mascot's own colours, sampled from the character sheet. */
export const TILLI_COLORS = {
  ink: '#5b3d27',
  skin: '#fbe39c',
  skinShade: '#f2cd78',
  leaf: '#d3cd86',
  leafShade: '#b7b062',
  shell: '#bcc78f',
  shellLight: '#d3dbab',
  shellShade: '#9eab70',
  shellInside: '#8d9862',
  rim: '#f6ecd2',
  cloud: '#fbf3df',
  heart: '#f3a48f',
  heartLight: '#f8c6b6',
  patch: '#f8ead0',
  cord: '#dca447',
  blush: '#f3a998',
  eye: '#3a2618',
  mouth: '#c95a4b',
  tongue: '#f08b7b',
  shadow: '#5b3d27',
} as const;

const C = TILLI_COLORS;
const STROKE = `stroke="${C.ink}" stroke-width="3.2" stroke-linejoin="round" stroke-linecap="round"`;

function cloud(x: number, y: number, s: number): string {
  return `<g transform="translate(${x} ${y}) scale(${s})" fill="${C.cloud}" stroke="${C.ink}" stroke-width="${2.2 / s}" stroke-opacity=".55">
    <path d="M-14 6 a7 7 0 0 1 2-13 a9 9 0 0 1 16-4 a8 8 0 0 1 12 6 a6 6 0 0 1 -1 11 z"/>
  </g>`;
}

function flower(x: number, y: number): string {
  const petals = [0, 72, 144, 216, 288]
    .map((a) => {
      const r = (a * Math.PI) / 180;
      return `<circle cx="${(x + Math.sin(r) * 7.2).toFixed(1)}" cy="${(y - Math.cos(r) * 7.2).toFixed(1)}" r="6.6"/>`;
    })
    .join('');
  return `<g class="t-charm-flower">
    <g fill="${C.heart}" ${STROKE} stroke-width="2.4">${petals}</g>
    <circle cx="${x}" cy="${y}" r="6.4" fill="${C.heart}"/>
    <path d="M${x} ${y + 4} v-7 M${x} ${y - 1} q-4 -1 -4 -5 M${x} ${y - 1} q4 -1 4 -5" stroke="${C.cloud}" stroke-width="2" fill="none" stroke-linecap="round"/>
  </g>`;
}

function face(mood: TilliMood): string {
  const closed = mood === 'sleeping';
  const eyes = closed
    ? `<g class="t-eyes" fill="none" stroke="${C.eye}" stroke-width="2.6" stroke-linecap="round">
        <path d="M92 74 q6 5 12 0"/><path d="M124 72 q6 5 12 0"/></g>`
    : `<g class="t-eyes"><g class="t-pupils">
        <ellipse cx="98" cy="70" rx="4.8" ry="6.4" fill="${C.eye}"/>
        <ellipse cx="130" cy="68" rx="4.8" ry="6.4" fill="${C.eye}"/>
        <circle cx="99.6" cy="67.4" r="1.7" fill="#fff"/>
        <circle cx="131.6" cy="65.4" r="1.7" fill="#fff"/>
      </g></g>`;
  const blush = `<g fill="${C.blush}" opacity=".6">
      <ellipse cx="86" cy="84" rx="7.5" ry="4.6"/><ellipse cx="143" cy="81" rx="7.5" ry="4.6"/></g>
    <g stroke="${C.mouth}" stroke-width="1.2" opacity=".55" stroke-linecap="round">
      <path d="M83 83 l-1.6 2.6 M87 83 l-1.6 2.6"/><path d="M140 80 l-1.6 2.6 M144 80 l-1.6 2.6"/></g>`;
  const open = `<path class="t-mouth-open" d="M107 80 Q114.5 95 122 79 Q114.5 83 107 80 Z" fill="${C.mouth}" stroke="${C.ink}" stroke-width="2.2" stroke-linejoin="round"/>
    <path class="t-mouth-open" d="M110.5 86.5 Q114.5 90.5 118.6 86 Q114.5 84.6 110.5 86.5 Z" fill="${C.tongue}"/>`;
  const smile = `<path class="t-mouth-smile" d="M108 81 q3.4 3.6 6.8 0 q3.4 3.6 6.8 0" fill="none" stroke="${C.ink}" stroke-width="2.2" stroke-linecap="round"/>`;
  const oh = `<ellipse class="t-mouth-oh" cx="115" cy="84" rx="3.6" ry="4.4" fill="${C.mouth}" stroke="${C.ink}" stroke-width="2"/>`;
  const sleepy = `<path d="M110 86 q5 2 10 0" fill="none" stroke="${C.ink}" stroke-width="2" stroke-linecap="round"/>`;

  let mouth: string;
  switch (mood) {
    case 'sleeping':
      mouth = sleepy;
      break;
    case 'curious':
      mouth = oh;
      break;
    case 'talking':
      mouth = `${open}${smile}`; // CSS alternates the two
      break;
    case 'arriving':
    case 'walk':
      mouth = smile;
      break;
    default:
      mouth = open;
  }
  return `<g class="t-face">${blush}${eyes}${mouth}</g>`;
}

function leaves(): string {
  return `<g class="t-leaves">
    <g class="t-leaf-sprout">
      <path d="M118 30 C121 12 142 4 158 10 C150 27 131 34 118 30 Z" fill="${C.leaf}" ${STROKE}/>
      <path d="M124 26 q13 -9 28 -13" fill="none" stroke="${C.leafShade}" stroke-width="1.8" stroke-linecap="round"/>
    </g>
    <g class="t-leaf-big">
      <path d="M114 34 C94 16 54 22 42 64 C64 72 100 62 114 34 Z" fill="${C.leaf}" ${STROKE}/>
      <path d="M108 37 q-26 8 -60 24" fill="none" stroke="${C.leafShade}" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M74 50 l-6 -7 M90 44 l-5 -7" fill="none" stroke="${C.leafShade}" stroke-width="1.4" stroke-linecap="round"/>
    </g>
  </g>`;
}

export interface TilliOptions {
  mood?: TilliMood;
  /** Hold a letter (arriving with a favor). */
  letter?: boolean;
  /** Extra marks around Tilli: "?", "zzz", "♪", sparkles. Default: by mood. */
  marks?: boolean;
  /** Accessible name. Empty string hides it from screen readers. */
  title?: string;
}

export function tilliSvg({
  mood = 'happy',
  letter,
  marks = true,
  title = 'Tilli',
}: TilliOptions = {}): string {
  const back = mood === 'away';
  const raise = mood === 'wave' || mood === 'arriving' || mood === 'celebrate';
  const holdLetter = letter ?? mood === 'arriving';
  const id = `t${Math.random().toString(36).slice(2, 8)}`;

  const head = `<g class="t-head-clip" clip-path="url(#${id}-open)"><g class="t-head">
      <circle cx="114" cy="76" r="50" fill="url(#${id}-skin)" ${STROKE}/>
      ${back ? `<path d="M72 98 q42 20 84 0" fill="none" stroke="${C.skinShade}" stroke-width="5" stroke-linecap="round" opacity=".7"/>` : `<g transform="translate(0 6)">${face(mood)}</g>`}
      ${leaves()}
    </g></g>`;

  const paws = back
    ? ''
    : `<g class="t-paws">
      <g class="t-paw-left"><ellipse cx="90" cy="111" rx="12.5" ry="9.5" fill="${C.skin}" ${STROKE}/>
        ${holdLetter ? `<g class="t-letter" transform="translate(62 90) rotate(-14)"><rect width="26" height="18" rx="3" fill="#fffaf0" ${STROKE} stroke-width="2.4"/><path d="M2 3 l11 8 l11 -8" fill="none" stroke="${C.ink}" stroke-width="2" stroke-linejoin="round"/><circle cx="13" cy="12" r="2.6" fill="${C.heart}"/></g>` : ''}
      </g>
      <g class="t-paw-right${raise ? ' is-up' : ''}">
        ${
          raise
            ? `<path d="M148 106 q13 -14 19 -32" fill="none" stroke="${C.ink}" stroke-width="13" stroke-linecap="round"/><path d="M148 106 q13 -14 19 -32" fill="none" stroke="${C.skin}" stroke-width="7.4" stroke-linecap="round"/><ellipse cx="168" cy="72" rx="10.5" ry="9.5" fill="${C.skin}" ${STROKE}/>`
            : `<ellipse cx="142" cy="108" rx="12.5" ry="9.5" fill="${C.skin}" ${STROKE}/>`
        }
      </g>
    </g>`;

  const extra = !marks
    ? ''
    : mood === 'sleeping'
      ? `<g class="t-mark t-zzz" fill="${C.ink}" font-family="Fredoka, Nunito, sans-serif" font-weight="700"><text x="168" y="54" font-size="16">z</text><text x="182" y="38" font-size="20">z</text><text x="198" y="20" font-size="24">z</text></g>`
      : mood === 'curious'
        ? `<g class="t-mark t-question"><text x="170" y="40" font-size="30" font-family="Fredoka, Nunito, sans-serif" font-weight="700" fill="${C.ink}">?</text><path d="M36 50 l-8 -6 M40 40 l-4 -9" stroke="${C.cord}" stroke-width="3.4" stroke-linecap="round"/></g>`
        : back
          ? `<g class="t-mark t-note" fill="${C.ink}"><path d="M176 30 v24 a6 5 0 1 1 -3 -4 v-24 l14 -4 v6 z"/></g>`
          : mood === 'celebrate'
            ? `<g class="t-mark t-sparkles" fill="${C.cord}">${[
                [34, 40, 1],
                [190, 50, 1.2],
                [184, 110, 0.8],
                [24, 104, 0.9],
              ]
                .map(
                  ([x, y, s]) =>
                    `<path transform="translate(${x} ${y}) scale(${s})" d="M0 -10 Q2 -2 10 0 Q2 2 0 10 Q-2 2 -10 0 Q-2 -2 0 -10 Z"/>`,
                )
                .join('')}</g>`
            : mood === 'happy' || mood === 'wave' || mood === 'arriving'
              ? `<g class="t-mark t-glee" stroke="${C.cord}" stroke-width="3.6" stroke-linecap="round"><path d="M176 50 l9 -7 M180 62 l11 -1 M172 38 l4 -10"/></g>`
              : '';

  return `<svg class="tilli__svg" viewBox="0 0 220 220" xmlns="http://www.w3.org/2000/svg" ${title ? `role="img" aria-label="${title}"` : 'aria-hidden="true"'}>
  <defs>
    <radialGradient id="${id}-shell" cx="38%" cy="30%" r="80%"><stop offset="0" stop-color="${C.shellLight}"/><stop offset=".55" stop-color="${C.shell}"/><stop offset="1" stop-color="${C.shellShade}"/></radialGradient>
    <radialGradient id="${id}-skin" cx="40%" cy="30%" r="75%"><stop offset="0" stop-color="#fff2c4"/><stop offset=".6" stop-color="${C.skin}"/><stop offset="1" stop-color="${C.skinShade}"/></radialGradient>
    <clipPath id="${id}-body"><ellipse cx="110" cy="134" rx="72" ry="60"/></clipPath>
    <clipPath id="${id}-open"><path d="M-40 -60 H260 V94 H170 A56 25 0 0 1 58 94 H-40 Z"/></clipPath>
  </defs>
  <ellipse class="t-shadow" cx="110" cy="206" rx="60" ry="7.5" fill="${C.shadow}" opacity=".16"/>
  <g class="t-body">
    <g class="t-feet">
      <ellipse class="t-foot t-foot-l" cx="88" cy="190" rx="14" ry="11" fill="${C.skin}" ${STROKE}/>
      <ellipse class="t-foot t-foot-r" cx="134" cy="190" rx="14" ry="11" fill="${C.skin}" ${STROKE}/>
    </g>
    <g class="t-shell">
      <ellipse cx="110" cy="134" rx="72" ry="60" fill="url(#${id}-shell)"/>
      <g clip-path="url(#${id}-body)">
        <path d="M44 118 q30 26 18 66 M152 96 q-10 44 28 72 M78 184 q40 -20 82 6" fill="none" stroke="${C.shellShade}" stroke-width="2.4" opacity=".55" stroke-linecap="round"/>
        ${back ? cloud(52, 122, 1.25) : cloud(46, 116, 1.25)}
        ${cloud(104, 172, 1)}
        ${cloud(186, 128, 1.15)}
        <g transform="translate(${back ? 134 : 142} 146) rotate(-8)">
          <rect x="-19" y="-17" width="38" height="34" rx="10" fill="${C.patch}" stroke="${C.ink}" stroke-width="2.2" stroke-opacity=".6"/>
          <path d="M0 10 C-14 1 -14 -11 -6 -11 C-3 -11 -1 -9 0 -6 C1 -9 3 -11 6 -11 C14 -11 14 1 0 10 Z" fill="${C.heart}" stroke="${C.ink}" stroke-width="2" stroke-opacity=".5"/>
          <path d="M-6 -6 q-3 1 -3 4" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round" opacity=".8"/>
        </g>
      </g>
      <ellipse cx="110" cy="134" rx="72" ry="60" fill="none" ${STROKE}/>
    </g>
    <g class="t-opening">
      <ellipse cx="114" cy="94" rx="56" ry="25" fill="${C.shellInside}"/>
      <path d="M58 94 A56 25 0 0 1 170 94" fill="none" stroke="${C.ink}" stroke-width="11"/>
      <path d="M58 94 A56 25 0 0 1 170 94" fill="none" stroke="${C.rim}" stroke-width="6"/>
    </g>
    ${head}
    <g class="t-rim-front">
      <path d="M58 94 A56 25 0 0 0 170 94" fill="none" stroke="${C.ink}" stroke-width="11"/>
      <path d="M58 94 A56 25 0 0 0 170 94" fill="none" stroke="${C.rim}" stroke-width="6"/>
    </g>
    <g class="t-charm">
      <path d="M${back ? 122 : 96} 116 C84 122 74 122 66 128" fill="none" stroke="${C.ink}" stroke-width="5.4" stroke-linecap="round"/>
      <path d="M${back ? 122 : 96} 116 C84 122 74 122 66 128" fill="none" stroke="${C.cord}" stroke-width="2.6" stroke-linecap="round"/>
      <g fill="${C.cord}" stroke="${C.ink}" stroke-width="1.8"><circle cx="62" cy="128" r="4.4"/><circle cx="70" cy="128" r="4.4"/><circle cx="66" cy="134" r="4.4"/></g>
      ${flower(62, 152)}
    </g>
    ${paws}
  </g>
  ${extra}
</svg>`;
}
