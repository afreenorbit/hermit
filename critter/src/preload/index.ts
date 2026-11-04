/** Exposes the keeper base URL and window controls to the renderer. Owner: C. */
import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('hermit', {
  keeperUrl: process.env.HERMIT_KEEPER_URL ?? 'http://127.0.0.1:47800',
});
