const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

// Sub-modules
const { setupBridge } = require('../bridge/api');
const { setupNotifications, sendLocalNotification } = require('../notifications/sender');
const { setupHotkeys, cleanUpHotkeys } = require('../hotkeys/manager');
const { createHUDWindow, closeHUDWindow, getHUDWindow } = require('../overlays/hud');
const { setupTray, updateTrayStatus } = require('../tray/menu');
const { setupAutostart } = require('../startup/launcher');

let mainWindow = null;
let pyProcess = null;
let sseRequest = null;
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

// Single Instance Protection
const additionalData = { myKey: 'jarvis-os-core' };
const gotTheLock = app.requestSingleInstanceLock(additionalData);

if (!gotTheLock) {
  app.quit();
  process.exit(0);
}

// App command line arguments support
const startHidden = process.argv.includes('--hidden');

function startBackend() {
  const isWin = process.platform === 'win32';
  const logFile = path.join(__dirname, '../../jarvis.log');

  try {
    const out = fs.openSync(logFile, 'a');
    const err = fs.openSync(logFile, 'a');

    if (isWin) {
      // Spawn python server inside WSL Ubuntu using wsl.exe
      pyProcess = spawn('wsl.exe', ['-e', 'bash', '-c', 'cd /home/pavan/jarvis/JarvisCore && python server.py'], {
        detached: true,
        stdio: ['ignore', out, err]
      });
    } else {
      const venvPython = '/home/pavan/jarvis/venv/bin/python';
      const serverScript = path.join(__dirname, '../../server.py');
      pyProcess = spawn(venvPython, [serverScript], {
        detached: true,
        stdio: ['ignore', out, err]
      });
    }

    if (pyProcess) {
      pyProcess.unref();
      console.log(`Backend spawned with PID: ${pyProcess.pid}`);
    }
  } catch (err) {
    console.error('Failed to spawn python backend process:', err);
  }
}

function stopBackend() {
  if (pyProcess) {
    try {
      // Kill entire process group since it was detached
      process.kill(-pyProcess.pid, 'SIGINT');
    } catch (e) {
      try {
        pyProcess.kill();
      } catch (err) {}
    }
    pyProcess = null;
  }
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    frame: false, // frameless UI for custom premium desktop feel
    transparent: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  const startUrl = `file://${path.join(__dirname, '../../frontend/dist/index.html')}`;

  mainWindow.loadURL(startUrl);

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide(); // Hide instead of close to run in background
    }
    return false;
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Event Streamer (SSE) listener
function startSSEListener() {
  if (sseRequest) {
    sseRequest.destroy();
  }

  console.log('Connecting to backend events stream at http://127.0.0.1:8765/api/events ...');
  
  sseRequest = http.get('http://127.0.0.1:8765/api/events', (res) => {
    if (res.statusCode !== 200) {
      console.log(`SSE returned status ${res.statusCode}. Retrying...`);
      setTimeout(startSSEListener, 3000);
      return;
    }

    let buffer = '';
    res.on('data', (chunk) => {
      buffer += chunk.toString();
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        const lines = part.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const dataStr = line.slice(6).trim();
              if (dataStr === '[DONE]') continue;
              const payload = JSON.parse(dataStr);

              // Broadcast to windows
              if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('server:event', payload);
              }
              const hud = getHUDWindow();
              if (hud && !hud.isDestroyed()) {
                hud.webContents.send('server:event', payload);
              }

              // Process tray menu/notifications
              handleSystemEvent(payload);
            } catch (e) {
              // Ignore partial parsing chunks
            }
          }
        }
      }
    });

    res.on('end', () => {
      console.log('SSE connection closed. Reconnecting...');
      setTimeout(startSSEListener, 3000);
    });
  });

  sseRequest.on('error', (err) => {
    console.log('SSE connection error. Retrying in 3s...', err.message);
    setTimeout(startSSEListener, 3000);
  });
}

let currentObjective = '';
let currentStatus = 'Standby';
let isAwaitingApproval = false;

function handleSystemEvent(payload) {
  const { event, data } = payload;
  if (!event) return;

  if (event === 'workflow.started' || event === 'objective.started') {
    currentObjective = data.objective || data.topic || '';
    currentStatus = 'Executing';
    sendLocalNotification('J.A.R.V.I.S. Objective Initiated', `Running: ${currentObjective}`);
    updateTrayStatus(currentStatus, currentObjective, isAwaitingApproval);
  } else if (event === 'task.started') {
    sendLocalNotification('J.A.R.V.I.S. Task Started', data.title);
  } else if (event === 'task.awaiting_approval') {
    isAwaitingApproval = true;
    currentStatus = 'Awaiting Approval';
    sendLocalNotification('Action Required, Sir', `Task awaiting permission: ${data.title}`);
    updateTrayStatus(currentStatus, currentObjective, isAwaitingApproval);
  } else if (event === 'task.completed') {
    isAwaitingApproval = false;
    currentStatus = 'Executing';
    updateTrayStatus(currentStatus, currentObjective, isAwaitingApproval);
  } else if (event === 'workflow.completed' || event === 'objective.completed') {
    currentStatus = 'Standby';
    isAwaitingApproval = false;
    sendLocalNotification('Objective Accomplished, Sir', currentObjective);
    currentObjective = '';
    updateTrayStatus(currentStatus, currentObjective, isAwaitingApproval);
  } else if (event === 'workflow.failed' || event === 'objective.failed') {
    currentStatus = 'Error/Halted';
    isAwaitingApproval = false;
    sendLocalNotification('Execution Halted', data.error || 'Workflow encountered an issue');
    updateTrayStatus(currentStatus, currentObjective, isAwaitingApproval);
  }
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

app.on('ready', () => {
  // 1. Autostart Launcher
  setupAutostart();

  // 2. Start JarvisCore Backend Subprocess
  startBackend();

  // 3. Create Windows
  createMainWindow();

  // Allow microphone media access inside electron shell
  session.defaultSession.setPermissionCheckHandler((webContents, permission, requestingOrigin) => {
    if (permission === 'media') return true;
    return false;
  });

  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') {
      callback(true);
    } else {
      callback(false);
    }
  });
  
  if (startHidden) {
    mainWindow.hide();
  }

  // 4. Create HUD
  const hudWindow = createHUDWindow(isDev);

  // 5. Setup Tray Menu
  setupTray(mainWindow, hudWindow, {
    onVoiceToggle: () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('voice:toggle');
      }
    },
    onApproveTask: () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('task:approve');
      }
    },
    onHUDToggle: () => {
      const hud = getHUDWindow();
      if (hud) {
        if (hud.isVisible()) {
          hud.hide();
        } else {
          hud.show();
        }
      } else {
        createHUDWindow(isDev);
      }
    }
  });

  // 6. Register Native OS Bridges (API and Notifications)
  setupBridge(ipcMain);
  setupNotifications(ipcMain);

  // 7. Register Global Hotkeys
  setupHotkeys(mainWindow, () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('voice:toggle');
    }
  });

  // 8. Start SSE loop to listen to Python backend events
  setTimeout(startSSEListener, 1500); // Allow backend to boot
});

// Window controls IPC
ipcMain.on('win:control', (event, action) => {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (action === 'minimize') {
    mainWindow.minimize();
  } else if (action === 'hide') {
    mainWindow.hide();
  } else if (action === 'show') {
    mainWindow.show();
  } else if (action === 'close') {
    mainWindow.hide(); // Map close window to hide for persistence
  }
});

app.on('window-all-closed', () => {
  // On macOS it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  app.isQuitting = true;
  cleanUpHotkeys();
  closeHUDWindow();
  stopBackend();
  if (sseRequest) {
    sseRequest.destroy();
  }
});
