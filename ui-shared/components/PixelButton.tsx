/** Two-state pressed button: shadow collapses, content shifts 4px. Owner: C. */
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

import type { IconName } from '../sprite/glyphs';
import { PixelIcon } from './PixelIcon';

export interface PixelButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'danger' | 'quest';
  size?: 'sm' | 'md' | 'lg';
  icon?: IconName;
  /** Icon-only buttons still need a name. */
  label?: string;
  children?: ReactNode;
}

export const PixelButton = forwardRef<HTMLButtonElement, PixelButtonProps>(function PixelButton(
  { variant = 'primary', size = 'md', icon, label, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={`hm-btn hm-btn--${variant} hm-btn--${size}${children ? '' : ' hm-btn--icon'} ${className ?? ''}`}
      {...rest}
    >
      {icon && <PixelIcon name={icon} scale={size === 'lg' ? 3 : 2} />}
      {children && <span>{children}</span>}
    </button>
  );
});
