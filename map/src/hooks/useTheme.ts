/** Light / dark toggle that defaults to the OS and remembers the choice. Owner: C. */
import { useMediaQuery } from '@hermit/ui';
import { useEffect, useState } from 'react';

type Choice = 'system' | 'light' | 'dark';
const KEY = 'hermit.theme';

function read(): Choice {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch {
    return 'system';
  }
}

export function useTheme(): { dark: boolean; toggle: () => void } {
  const [choice, setChoice] = useState<Choice>(read);
  const osDark = useMediaQuery('(prefers-color-scheme: dark)');
  const dark = choice === 'system' ? osDark : choice === 'dark';

  useEffect(() => {
    const root = document.documentElement;
    if (choice === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', choice);
  }, [choice]);

  const toggle = (): void => {
    const next: Choice = dark ? 'light' : 'dark';
    setChoice(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* fine: it just won't be remembered */
    }
  };

  return { dark, toggle };
}
