/** Exposes the keeper base URL and window controls to the renderers. Owner: C. */
import { contextBridge, ipcRenderer, type IpcRendererEvent } from 'electron';

type Channel = 'cursor' | 'sound-toggle' | 'sound';

const api = {
  keeperUrl: process.env.HERMIT_KEEPER_URL ?? 'http://127.0.0.1:47800',
  chatUrl: process.env.HERMIT_CHAT_URL ?? null,
  /** Pointer is over the sprite or dialog: stop clicking through. */
  setMouseOver: (over: boolean): void => ipcRenderer.send('hermit:mouse', over),
  setVisible: (visible: boolean): void => ipcRenderer.send('hermit:visible', visible),
  dragStart: (): void => ipcRenderer.send('hermit:drag-start'),
  dragEnd: (): void => ipcRenderer.send('hermit:drag-end'),
  panel: (open: boolean): void => ipcRenderer.send('hermit:panel', open),
  setConnected: (connected: boolean): void => ipcRenderer.send('hermit:connected', connected),
  soundState: (on: boolean): void => ipcRenderer.send('hermit:sound-state', on),
  openExternal: (url: string): void => ipcRenderer.send('hermit:open-external', url),
  on: (channel: Channel, cb: (value: unknown) => void): (() => void) => {
    const listener = (_e: IpcRendererEvent, value: unknown): void => cb(value);
    ipcRenderer.on(`hermit:${channel}`, listener);
    return () => ipcRenderer.off(`hermit:${channel}`, listener);
  },
};

export type HermitBridge = typeof api;

contextBridge.exposeInMainWorld('hermit', api);
