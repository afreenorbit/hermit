import '@hermit/ui/styles/fonts.css';
import '@hermit/ui/styles/theme.css';
import '../shared/critter.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { PanelWindow } from './PanelWindow';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PanelWindow />
  </StrictMode>,
);
