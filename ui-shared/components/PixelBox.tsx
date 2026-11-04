/** 9-slice-style pixel container with stepped corners and a hard shadow. Owner: C. */
import type { ElementType, HTMLAttributes, ReactNode } from 'react';

export type PixelBoxVariant = 'paper' | 'night' | 'quest' | 'ink' | 'inset';

export interface PixelBoxProps extends HTMLAttributes<HTMLElement> {
  variant?: PixelBoxVariant;
  /** Name tab on the top-left edge, RPG dialog style. */
  tab?: ReactNode;
  as?: ElementType;
  /** No hard drop shadow (nested boxes). */
  flat?: boolean;
}

export function PixelBox({
  variant = 'paper',
  tab,
  as: Tag = 'div',
  flat,
  className,
  children,
  ...rest
}: PixelBoxProps) {
  return (
    <Tag
      className={`hm-box hm-box--${variant}${flat ? ' hm-box--flat' : ''}${tab ? ' hm-box--tabbed' : ''} ${className ?? ''}`}
      {...rest}
    >
      {tab && <span className="hm-box__tab">{tab}</span>}
      {children}
    </Tag>
  );
}
