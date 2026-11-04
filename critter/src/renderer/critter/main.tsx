import '@hermit/ui/styles/fonts.css';
import '@hermit/ui/styles/theme.css';
import '../shared/critter.css';

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { inElectron } from '../shared/bridge';
import { CritterWindow } from './CritterWindow';

if (!inElectron) document.documentElement.classList.add('web-preview');
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CritterWindow />
  </StrictMode>,
);
