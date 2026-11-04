/**
 * @hermit/ui — the one design system both the critter and the map use.
 * Owner: C. See plan.md §3.6.
 */
export * from './palette';
export * from './lib/format';
export { fnv1a, hash2, mulberry32 } from './lib/hash';
export { sound, type SoundName } from './lib/sound';

export {
  borrowedShell,
  patternB,
  patternGrid,
  pieceColors,
  pieceHour,
  renderShellGrid,
  segmentLength,
  type ShellGrid,
  type ShellOptions,
  type ShellPiece,
  type ShellPieceInput,
} from './shell/renderShellGrid';
export { toCanvas, toImageData, toRuns, toSVG, RGB } from './shell/adapters';
export { hostAccent, pixelAvatar } from './avatar/pixelAvatar';
export * from './sprite/hermit';
export * from './sprite/glyphs';

export * from './components/hooks';
export { BrainBadge, DepartureChip, StatusChip, type QuestStatus } from './components/Chips';
export { DialogBox, type DialogBoxProps } from './components/DialogBox';
export { HermitSprite, SpriteAnimator } from './components/HermitSprite';
export { PixelAvatar } from './components/PixelAvatar';
export { PixelBox, type PixelBoxProps } from './components/PixelBox';
export { PixelButton, type PixelButtonProps } from './components/PixelButton';
export { PixelCanvas } from './components/PixelCanvas';
export { PixelGridSvg, PixelIcon } from './components/PixelIcon';
export { PixelTabs, PixelToggleGroup, type PixelTab, type ToggleItem } from './components/Controls';
export { QuestCard } from './components/QuestCard';
export { ShellView } from './components/ShellView';
export { StatTile } from './components/StatTile';
export { Ticker } from './components/Ticker';

export { Tilli, type TilliProps } from './components/Tilli';
export {
  tilliSvg,
  TILLI_COLORS,
  TILLI_MOODS,
  type TilliMood,
  type TilliOptions,
} from './mascot/tilli';

export { PocketHermit, MOOD_LABEL } from './components/PocketHermit';
export type { Mood, PocketHermitProps } from './components/PocketHermit';
