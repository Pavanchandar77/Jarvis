const { BrowserWindow, screen } = require('electron');
const path = require('path');

let hudWindow = null;

function createHUDWindow(isDev) {
  if (hudWindow) return hudWindow;

  const { width } = screen.getPrimaryDisplay().workAreaSize;
  
  hudWindow = new BrowserWindow({
    width: 340,
    height: 220,
    x: width - 360,
    y: 40,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    focusable: false,
    resizable: false,
    skipTaskbar: true,
    webPreferences: {
      preload: path.join(__dirname, '../electron/preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // Make it ignore mouse events for true click-through
  hudWindow.setIgnoreMouseEvents(true, { forward: true });

  const startUrl = `file://${path.join(__dirname, '../../frontend/dist/index.html')}?hud=true`;

  hudWindow.loadURL(startUrl);

  hudWindow.on('closed', () => {
    hudWindow = null;
  });

  return hudWindow;
}

function getHUDWindow() {
  return hudWindow;
}

function closeHUDWindow() {
  if (hudWindow) {
    hudWindow.close();
    hudWindow = null;
  }
}

module.exports = { createHUDWindow, getHUDWindow, closeHUDWindow };
