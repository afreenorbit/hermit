# Pixel components — owner: C

PixelBox · DialogBox · PixelButton · QuestCard · StatTile · BrainBadge ·
DepartureChip · StatusChip · PixelAvatar · ShellView · HermitSprite ·
SpriteAnimator · Ticker · PixelTabs · PixelToggleGroup · PixelIcon · PixelCanvas

Styles live in `../styles/components.css` (plain CSS, `hm-` prefix) so they work
in any app that imports `@hermit/ui/styles/theme.css`. Specs: plan.md §3.6.

There is no Storybook yet: the map (`pnpm dev:map`) and the critter browser
preview (`pnpm --filter @hermit/critter dev:web`) exercise every component
against the committed fixtures and the mock keeper.
