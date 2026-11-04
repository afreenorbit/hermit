/** A favor, shown as a quest with the shell piece it will create. Owner: C. */
import { useMemo } from 'react';

import { renderShellGrid, type ShellPieceInput } from '../shell/renderShellGrid';
import { StatusChip, type QuestStatus } from './Chips';
import { PixelCanvas } from './PixelCanvas';
import { PixelIcon } from './PixelIcon';

export interface QuestCardProps {
  text: string;
  /** Display name of whoever left it ("HERMIT" for wild favors). */
  from: string;
  status?: QuestStatus;
  /** Piece this favor would add — rendered as a tiny shell preview. */
  reward?: ShellPieceInput | null;
  compact?: boolean;
}

export function QuestCard({ text, from, status = 'open', reward, compact }: QuestCardProps) {
  const preview = useMemo(
    () => (reward ? renderShellGrid([reward], { size: 24 }) : null),
    [reward],
  );
  return (
    <article className={`hm-quest hm-quest--${status}${compact ? ' hm-quest--compact' : ''}`}>
      <header className="hm-quest__head">
        <PixelIcon name="quest" className="hm-quest__mark" />
        <span className="hm-quest__from">QUEST FROM {from.toUpperCase()}</span>
        <StatusChip status={status} />
      </header>
      <p className="hm-quest__text">“{text}”</p>
      {preview && !compact && (
        <footer className="hm-quest__reward">
          <span>REWARD</span>
          <PixelCanvas grid={preview} scale={2} label="Shell piece this quest will add" />
        </footer>
      )}
    </article>
  );
}
