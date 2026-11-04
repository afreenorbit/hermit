/**
 * Critter main process. Owner: C, Phase 6.2.
 *
 * A transparent, frameless, always-on-top, click-through window holding a 128px
 * creature, plus a panel window that opens on click. Position is remembered per
 * display. The critter only exists while this host holds the soul.
 */
import { app, BrowserWindow } from 'electron';

const KEEPER_BASE_URL = process.env.HERMIT_KEEPER_URL ?? 'http://127.0.0.1:47800';

function createCritterWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 160,
    height: 160,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    webPreferences: { preload: `${__dirname}/../preload/index.js` },
  });
  win.setIgnoreMouseEvents(true, { forward: true });
  // TODO(C): load the renderer, remember position, tray menu, show/hide on soul events
  return win;
}

app.whenReady().then(() => {
  console.log('keeper at', KEEPER_BASE_URL);
  createCritterWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
