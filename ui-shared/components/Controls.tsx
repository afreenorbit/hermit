/** PixelTabs and PixelToggleGroup — Radix behaviour, pixel styling. Owner: C. */
import * as Tabs from '@radix-ui/react-tabs';
import * as ToggleGroup from '@radix-ui/react-toggle-group';
import type { ReactNode } from 'react';

export interface PixelTab {
  id: string;
  label: string;
  content: ReactNode;
  badge?: ReactNode;
}

export function PixelTabs({
  tabs,
  value,
  onValueChange,
  label,
}: {
  tabs: PixelTab[];
  value?: string;
  onValueChange?: (v: string) => void;
  label: string;
}) {
  return (
    <Tabs.Root
      className="hm-tabs"
      defaultValue={tabs[0]?.id}
      {...(value !== undefined ? { value } : {})}
      {...(onValueChange ? { onValueChange } : {})}
    >
      <Tabs.List className="hm-tabs__list" aria-label={label}>
        {tabs.map((t) => (
          <Tabs.Trigger key={t.id} value={t.id} className="hm-tabs__tab">
            {t.label}
            {t.badge}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      {tabs.map((t) => (
        <Tabs.Content key={t.id} value={t.id} className="hm-tabs__panel">
          {t.content}
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}

export interface ToggleItem {
  value: string;
  label: ReactNode;
  title?: string;
}

export function PixelToggleGroup({
  items,
  value,
  onValueChange,
  label,
  required = false,
}: {
  items: ToggleItem[];
  value: string;
  onValueChange: (v: string) => void;
  label: string;
  /** Pressing the active item keeps it, instead of falling back to the first. */
  required?: boolean;
}) {
  return (
    <ToggleGroup.Root
      type="single"
      className="hm-toggles"
      value={value}
      onValueChange={(v) => {
        if (!v && required) return;
        onValueChange(v || (items[0]?.value ?? ''));
      }}
      aria-label={label}
    >
      {items.map((i) => (
        <ToggleGroup.Item key={i.value} value={i.value} className="hm-toggle" title={i.title}>
          {i.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
