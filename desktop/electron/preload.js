const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  openApp: (name) => ipcRenderer.invoke('os:open-app', name),
  openFolder: (path) => ipcRenderer.invoke('os:open-folder', path),
  openFile: (path) => ipcRenderer.invoke('os:open-file', path),
  showNotification: (title, body) => ipcRenderer.send('os:show-notification', { title, body }),
  windowControl: (action) => ipcRenderer.send('win:control', action),
  onServerEvent: (callback) => ipcRenderer.on('server:event', (event, value) => callback(value)),
  onVoiceToggle: (callback) => ipcRenderer.on('voice:toggle', () => callback()),
  onApproveTask: (callback) => ipcRenderer.on('task:approve', () => callback()),
});

