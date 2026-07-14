/**
 * preload.js — Electron context bridge
 *
 * Exposes safe, whitelisted Electron APIs to the Spark web UI
 * without giving the renderer full Node.js access.
 */

'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// ── Window controls ──────────────────────────────────────────────────────────
contextBridge.exposeInMainWorld('electronAPI', {
  // Window controls
  minimize:   () => ipcRenderer.send('win:minimize'),
  maximize:   () => ipcRenderer.send('win:maximize'),
  close:      () => ipcRenderer.send('win:close'),    // hides to tray
  winControl: (action) => ipcRenderer.send('win:control', action),
  showHalo:   () => ipcRenderer.send('halo:show'),
  hideHalo:   () => ipcRenderer.send('halo:hide'),

  // App metadata
  getVersion:       () => ipcRenderer.invoke('app:version'),
  getServerUrl:     () => ipcRenderer.invoke('app:serverUrl'),
  isBackendReady:   () => ipcRenderer.invoke('app:isBackendReady'),

  // Detection flags
  isElectron: true,
  platform:   process.platform,
});

// ── Legacy compatibility (some parts of Spark use window.electron) ────────
contextBridge.exposeInMainWorld('electron', {
  send: (channel, ...args) => {
    const allowed = ['win:minimize', 'win:maximize', 'win:close', 'win:control', 'halo:show', 'halo:hide'];
    if (allowed.includes(channel)) ipcRenderer.send(channel, ...args);
  },
  invoke: (channel, ...args) => {
    const allowed = ['app:version', 'app:serverUrl', 'app:isBackendReady'];
    if (allowed.includes(channel)) return ipcRenderer.invoke(channel, ...args);
    return Promise.reject(new Error(`IPC channel not allowed: ${channel}`));
  },
  isElectron: true,
  platform:   process.platform,
});
