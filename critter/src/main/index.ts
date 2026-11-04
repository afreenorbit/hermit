/**
 * Critter main process. Owner: C, Phase 6.2.
 *
 * A transparent, frameless, always-on-top, click-through window holding the
 * creature, plus a panel window ("Hermit's menu") that opens on click or from
 * the tray. Position is remembered and snapped back on-screen if a monitor
 * goes away. The creature window is only shown while this host holds the soul
 * — the renderer decides that from the keeper's events and tells us.
 */
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  app,
  BrowserWindow,
  ipcMain,
  Menu,
  nativeImage,
  screen,
  shell,
  Tray,
  type Rectangle,
} from 'electron';

const KEEPER_BASE_URL = process.env.HERMIT_KEEPER_URL ?? 'http://127.0.0.1:47800';
const CRITTER = { w: 320, h: 300 };
const PANEL = { w: 360, h: 520 };
const EDGE = 24;

let critter: BrowserWindow | null = null;
let panel: BrowserWindow | null = null;
let tray: Tray | null = null;
let connected = false;
let soundOn = false;
let wantVisible = false;
let snoozeUntil = 0;
let snoozeTimer: NodeJS.Timeout | undefined;
let cursorTimer: NodeJS.Timeout | undefined;
let dragTimer: NodeJS.Timeout | undefined;

// ---------------------------------------------------------------------------
// position memory
const posFile = (): string => join(app.getPath('userData'), 'critter-position.json');

function defaultPosition(): { x: number; y: number } {
  const wa = screen.getPrimaryDisplay().workArea;
  return { x: wa.x + wa.width - CRITTER.w - EDGE, y: wa.y + wa.height - CRITTER.h - EDGE };
}

function onScreen(r: Rectangle): boolean {
  return screen.getAllDisplays().some(({ workArea: wa }) => {
    const cx = r.x + r.width / 2;
    const cy = r.y + r.height * 0.75; // the sprite sits low in the window
    return cx >= wa.x && cx <= wa.x + wa.width && cy >= wa.y && cy <= wa.y + wa.height;
  });
}

function loadPosition(): { x: number; y: number } {
  try {
    if (existsSync(posFile())) {
      const p = JSON.parse(readFileSync(posFile(), 'utf8')) as { x: number; y: number };
      if (onScreen({ ...p, width: CRITTER.w, height: CRITTER.h })) return p;
    }
  } catch {
    /* corrupt file: fall back */
  }
  return defaultPosition();
}

function savePosition(): void {
  if (!critter) return;
  const [x, y] = critter.getPosition();
  try {
    writeFileSync(posFile(), JSON.stringify({ x, y }));
  } catch {
    /* not fatal */
  }
}

function snapOnScreen(): void {
  if (critter && !onScreen(critter.getBounds())) {
    const p = defaultPosition();
    critter.setPosition(p.x, p.y);
    savePosition();
  }
}

// ---------------------------------------------------------------------------
// windows
function load(win: BrowserWindow, name: 'critter' | 'panel'): void {
  const dev = process.env.ELECTRON_RENDERER_URL;
  if (!app.isPackaged && dev) void win.loadURL(`${dev}/${name}/index.html`);
  else void win.loadFile(join(__dirname, `../renderer/${name}/index.html`));
}

const webPreferences = {
  preload: join(__dirname, '../preload/index.js'),
  sandbox: false,
  contextIsolation: true,
  nodeIntegration: false,
};

function createCritterWindow(): BrowserWindow {
  const { x, y } = loadPosition();
  const win = new BrowserWindow({
    width: CRITTER.w,
    height: CRITTER.h,
    x,
    y,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    resizable: false,
    movable: true,
    focusable: false,
    skipTaskbar: true,
    hasShadow: false,
    show: false,
    webPreferences,
  });
  win.setAlwaysOnTop(true, 'floating');
  if (process.platform === 'darwin')
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  // Transparent pixels click through; the renderer flips this while the
  // pointer is over the sprite or its dialog box.
  win.setIgnoreMouseEvents(true, { forward: true });
  load(win, 'critter');
  return win;
}

function openPanel(): void {
  if (panel && !panel.isDestroyed()) {
    panel.show();
    panel.focus();
    return;
  }
  panel = new BrowserWindow({
    width: PANEL.w,
    height: PANEL.h,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    show: false,
    backgroundColor: '#1a1c2c',
    title: "Hermit's menu",
    webPreferences,
  });
  // Beside the creature, kept inside the same display.
  const anchor = critter?.getBounds() ?? {
    ...defaultPosition(),
    width: CRITTER.w,
    height: CRITTER.h,
  };
  const wa = screen.getDisplayMatching(anchor).workArea;
  const px = Math.min(Math.max(wa.x, anchor.x - PANEL.w + 40), wa.x + wa.width - PANEL.w);
  const py = Math.min(
    Math.max(wa.y, anchor.y + anchor.height - PANEL.h),
    wa.y + wa.height - PANEL.h,
  );
  panel.setPosition(Math.round(px), Math.round(py));
  panel.once('ready-to-show', () => panel?.show());
  panel.on('closed', () => (panel = null));
  load(panel, 'panel');
}

function applyVisibility(): void {
  if (!critter) return;
  const show = wantVisible && Date.now() >= snoozeUntil;
  if (show && !critter.isVisible()) {
    snapOnScreen();
    critter.showInactive();
    startCursor();
  } else if (!show && critter.isVisible()) {
    critter.hide();
    stopCursor();
  }
}

// The renderer gets the cursor position so Hermit's eyes can follow it.
function startCursor(): void {
  stopCursor();
  cursorTimer = setInterval(() => {
    if (!critter || critter.isDestroyed()) return;
    const p = screen.getCursorScreenPoint();
    const b = critter.getBounds();
    critter.webContents.send('hermit:cursor', { x: p.x - b.x, y: p.y - b.y });
  }, 120);
}
function stopCursor(): void {
  if (cursorTimer) clearInterval(cursorTimer);
  cursorTimer = undefined;
}

// ---------------------------------------------------------------------------
// tray — a 16x16 Hermit drawn from pixels, grey while the keeper is unreachable
const TRAY_ART = [
  '................',
  '......k..k......',
  '.....kwk.kwk....',
  '.....kkk.kkk....',
  '...kkkk..k......',
  '..kmmmmk.k......',
  '.kmdmmdmkeek....',
  'kmmdmmdmkeeek.kk',
  'kmmddmmkeeeeeksk',
  'kmmmmmkeeeeeekk.',
  '.kmmmkeeeeeeek..',
  '..kkkkreerreek..',
  '....krkrkrkrk...',
  '....k.k.k.k.k...',
  '................',
  '................',
];
const TRAY_COLORS: Record<string, [number, number, number]> = {
  k: [0x1a, 0x1c, 0x2c],
  w: [0xf4, 0xf4, 0xf4],
  m: [0x94, 0xb0, 0xc2],
  d: [0x56, 0x6c, 0x86],
  e: [0xef, 0x7d, 0x57],
  r: [0xb1, 0x3e, 0x53],
  s: [0xff, 0xcd, 0x75],
};

function trayIcon(grey: boolean): Electron.NativeImage {
  const size = 16;
  const buf = Buffer.alloc(size * size * 4);
  TRAY_ART.forEach((row, y) => {
    for (let x = 0; x < size; x++) {
      const c = TRAY_COLORS[row[x] ?? '.'];
      if (!c) continue;
      let [r, g, b] = c;
      if (grey) r = g = b = Math.round(0.3 * r + 0.59 * g + 0.11 * b);
      const o = (y * size + x) * 4;
      buf[o] = b; // BGRA
      buf[o + 1] = g;
      buf[o + 2] = r;
      buf[o + 3] = 255;
    }
  });
  return nativeImage.createFromBitmap(buf, { width: size, height: size });
}

function rebuildTray(): void {
  if (!tray) return;
  tray.setImage(trayIcon(!connected));
  tray.setToolTip(connected ? 'Hermit' : 'Hermit — keeper not running');
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Open Hermit's menu", click: openPanel },
      {
        label: 'Hermit, please go',
        enabled: connected,
        click: () =>
          void fetch(`${KEEPER_BASE_URL}/v1/depart`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ reason: 'manual' }),
          }).catch(() => undefined),
      },
      {
        label: Date.now() < snoozeUntil ? 'Hidden for now — show again' : 'Hide for 1 hour',
        click: () => {
          clearTimeout(snoozeTimer);
          if (Date.now() < snoozeUntil) snoozeUntil = 0;
          else {
            snoozeUntil = Date.now() + 3600_000;
            snoozeTimer = setTimeout(() => {
              snoozeUntil = 0;
              applyVisibility();
              rebuildTray();
            }, 3600_000);
          }
          applyVisibility();
          rebuildTray();
        },
      },
      {
        label: 'Sound',
        type: 'checkbox',
        checked: soundOn,
        click: () => critter?.webContents.send('hermit:sound-toggle', null),
      },
      { type: 'separator' },
      { label: 'Quit critter (the keeper keeps running)', click: () => app.quit() },
    ]),
  );
}

// ---------------------------------------------------------------------------
// ipc
ipcMain.on('hermit:mouse', (_e, over: boolean) => {
  critter?.setIgnoreMouseEvents(!over, { forward: true });
});

ipcMain.on('hermit:visible', (_e, visible: boolean) => {
  wantVisible = !!visible;
  applyVisibility();
});

ipcMain.on('hermit:drag-start', () => {
  if (!critter) return;
  const start = screen.getCursorScreenPoint();
  const [wx, wy] = critter.getPosition();
  const dx = start.x - wx!;
  const dy = start.y - wy!;
  clearInterval(dragTimer);
  dragTimer = setInterval(() => {
    const p = screen.getCursorScreenPoint();
    critter?.setPosition(p.x - dx, p.y - dy);
  }, 16);
});

ipcMain.on('hermit:drag-end', () => {
  clearInterval(dragTimer);
  dragTimer = undefined;
  snapOnScreen();
  savePosition();
});

ipcMain.on('hermit:panel', (_e, open: boolean) => {
  if (open) openPanel();
  else panel?.close();
});

ipcMain.on('hermit:connected', (_e, c: boolean) => {
  if (connected === !!c) return;
  connected = !!c;
  rebuildTray();
});

ipcMain.on('hermit:sound-state', (_e, on: boolean) => {
  soundOn = !!on;
  panel?.webContents.send('hermit:sound', soundOn);
  critter?.webContents.send('hermit:sound', soundOn);
  rebuildTray();
});

ipcMain.on('hermit:open-external', (_e, url: string) => {
  if (/^https?:\/\//.test(url)) void shell.openExternal(url);
});

// ---------------------------------------------------------------------------
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', openPanel);
  app.whenReady().then(() => {
    if (process.platform === 'darwin') app.dock?.hide();
    console.log('keeper at', KEEPER_BASE_URL);
    critter = createCritterWindow();
    tray = new Tray(trayIcon(true));
    tray.on('click', openPanel);
    rebuildTray();
    screen.on('display-removed', snapOnScreen);
    screen.on('display-metrics-changed', snapOnScreen);
  });
  // Closing the panel must not quit; only the tray's Quit does.
  app.on('window-all-closed', () => undefined);
  app.on('before-quit', savePosition);
}
