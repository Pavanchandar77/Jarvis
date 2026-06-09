/**
 * main.js — Spark Desktop (Electron main process)
 *
 * Responsibilities:
 *  - Spawn and supervise the Python/uvicorn backend
 *  - Show a beautiful splash screen while waiting for it to be ready
 *  - Create the main BrowserWindow once the backend is healthy
 *  - System-tray integration (hide to tray on close)
 *  - IPC for custom window controls
 *  - Auto-launch on Windows login (via registry shortcut)
 */

'use strict';

const { app, BrowserWindow, Tray, Menu, dialog, ipcMain, shell, nativeImage } = require('electron');
const { autoUpdater } = require('electron-updater');
const path   = require('path');
const { spawn, exec } = require('child_process');
const http   = require('http');
const fs     = require('fs');

// ─── State ────────────────────────────────────────────────────────────────────

let mainWindow    = null;
let splashWindow  = null;
let tray          = null;
let backendProcess = null;
let isQuitting    = false;
let backendReady  = false;

const PORT       = parseInt(process.env.APP_PORT  || '7000', 10);
const HOST       = process.env.APP_BIND            || '127.0.0.1';
const SERVER_URL = `http://${HOST}:${PORT}`;

// ─── Logging ──────────────────────────────────────────────────────────────────

const appRoot = app.isPackaged 
  ? path.join(process.resourcesPath, 'app') 
  : __dirname;

const logDir = app.isPackaged 
  ? path.join(app.getPath('userData'), 'logs') 
  : path.join(__dirname, 'logs');
if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });

const logStream = fs.createWriteStream(path.join(logDir, 'electron-backend.log'), { flags: 'a' });

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  process.stdout.write(line);
  logStream.write(line);
}

// ─── Single-instance lock ─────────────────────────────────────────────────────

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  // Use process.exit() not app.quit() — app.quit() is async and
  // app.whenReady() could still fire before it finishes, causing
  // killPortIfBusy() to murder the running instance's backend.
  log('Another instance is already running. Focusing existing window and exiting.');
  process.exit(0);
}
app.on('second-instance', () => {
  // Someone tried to run a second instance — bring existing window to front
  if (mainWindow) {
    if (!mainWindow.isVisible()) mainWindow.show();
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ─── Utilities ────────────────────────────────────────────────────────────────

/**
 * Kill whatever process is already holding our port so we always get a clean start.
 */
function killPortIfBusy(port, cb) {
  const cmd = process.platform === 'win32'
    ? `for /f "tokens=5" %a in ('netstat -aon ^| findstr :${port}') do @taskkill /F /PID %a 2>nul`
    : `lsof -ti:${port} | xargs kill -9 2>/dev/null`;
  exec(cmd, () => cb()); // ignore errors — port may simply be free
}

function resolveIcon(names) {
  for (const name of names) {
    const p = path.join(__dirname, 'static', name);
    if (fs.existsSync(p)) return p;
  }
  return null; // electron will use a default
}

// ─── Backend ─────────────────────────────────────────────────────────────────

function startBackend() {
  log('=== Starting Spark backend server ===');

  // Prefer venv python; fall back to system python
  const venvScripts = [
    path.join(appRoot, 'venv', 'Scripts', 'python.exe'), // Windows
    path.join(appRoot, 'venv', 'bin', 'python'),         // macOS/Linux
  ];
  let pythonPath = venvScripts.find(p => fs.existsSync(p)) || 'python';
  log(`Python: ${pythonPath}`);

  backendProcess = spawn(pythonPath, [
    '-m', 'uvicorn',
    'app:app',
    '--host', HOST,
    '--port', PORT.toString(),
    '--log-level', 'info',
  ], {
    cwd: appRoot,
    env: {
      ...process.env,
      PYTHONUNBUFFERED:   '1',
      LOCALHOST_BYPASS:   'true',  // skip auth for loopback requests from Electron
    },
  });

  backendProcess.stdout.on('data', d => log(`[py] ${d.toString().trim()}`));
  backendProcess.stderr.on('data', d => log(`[py] ${d.toString().trim()}`));

  backendProcess.on('close', (code) => {
    log(`Backend exited with code ${code}`);
    backendReady = false;

    if (!isQuitting) {
      dialog.showMessageBox({
        type: 'error',
        title: 'Spark — Backend Stopped',
        message: `The backend server stopped unexpectedly (exit code ${code}).`,
        detail: 'Check logs/electron-backend.log for details.',
        buttons: ['View Logs', 'Restart', 'Quit'],
        defaultId: 1,
      }).then(({ response }) => {
        if (response === 0) shell.openPath(path.join(logDir, 'electron-backend.log'));
        if (response === 1) { startBackend(); pollBackend(onBackendReady); }
        if (response === 2) { isQuitting = true; app.quit(); }
      });
    }
  });
}

// ─── Health-check polling ─────────────────────────────────────────────────────

function checkBackendReady(cb) {
  const req = http.get(`${SERVER_URL}/api/ready`, { timeout: 1500 }, (res) => {
    let data = '';
    res.on('data', c => { data += c; });
    res.on('end', () => {
      try {
        cb(res.statusCode === 200 && JSON.parse(data).ready === true);
      } catch { cb(false); }
    });
  });
  req.on('error', () => cb(false));
  req.on('timeout', () => { req.destroy(); cb(false); });
}

function pollBackend(cb, maxMs = 60_000, intervalMs = 500) {
  const deadline = Date.now() + maxMs;
  const timer = setInterval(() => {
    checkBackendReady((ready) => {
      if (ready) {
        clearInterval(timer);
        cb(true);
      } else if (Date.now() >= deadline) {
        clearInterval(timer);
        cb(false);
      }
    });
  }, intervalMs);
}

// ─── Windows ──────────────────────────────────────────────────────────────────

function createSplash() {
  splashWindow = new BrowserWindow({
    width:           480,
    height:          340,
    resizable:       false,
    frame:           false,
    transparent:     false,
    alwaysOnTop:     true,
    center:          true,
    backgroundColor: '#0d0d1a',
    webPreferences:  { nodeIntegration: false, contextIsolation: true },
  });

  const splashPath = path.join(__dirname, 'static', 'splash.html');
  splashWindow.loadFile(splashPath);
  splashWindow.once('ready-to-show', () => splashWindow.show());

  splashWindow.on('closed', () => { splashWindow = null; });
}

function createMainWindow() {
  const iconPath = resolveIcon(['icon-512.png', 'icon-192.png', 'icon.ico']);

  const isMac = process.platform === 'darwin';

  mainWindow = new BrowserWindow({
    width:           1280,
    height:          860,
    minWidth:        900,
    minHeight:       600,
    title:           'Spark',
    icon:            iconPath || undefined,
    // Native OS frame — gives real minimize/maximize/close on Windows & Linux
    frame:           true,
    // On macOS keep traffic lights; on Windows use the native chrome
    titleBarStyle:   isMac ? 'hiddenInset' : 'default',
    backgroundColor: '#0d0d1a',
    show:            false,
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      preload:          path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.removeMenu();

  mainWindow.once('ready-to-show', () => {
    // Fade from splash to main
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
    }
    mainWindow.show();
    mainWindow.center();
    log('Main window displayed.');
  });

  mainWindow.loadURL(SERVER_URL);

  // Clicking the close button hides to tray instead of quitting
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      // First-time hint
      if (tray && !mainWindow._trayHintShown) {
        mainWindow._trayHintShown = true;
        tray.displayBalloon({
          iconType: 'info',
          title:    'Spark is still running',
          content:  'Double-click the tray icon to reopen.',
        });
      }
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // Open external links in the system browser
    if (!url.startsWith(SERVER_URL)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });
}

function createTray() {
  const iconPath = resolveIcon(['icon-192.png', 'icon-512.png', 'icon.ico']);
  tray = new Tray(iconPath ? nativeImage.createFromPath(iconPath).resize({ width: 16 }) : nativeImage.createEmpty());

  const rebuild = () => {
    const menuTemplate = [
      {
        label: 'Open Spark',
        click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } },
      },
      {
        label: 'Restart Backend',
        click: () => {
          log('User requested backend restart…');
          if (backendProcess) backendProcess.kill();
          startBackend();
          if (mainWindow) mainWindow.loadURL(SERVER_URL);
        },
      },
      {
        label: 'Open Log File',
        click: () => shell.openPath(path.join(logDir, 'electron-backend.log')),
      },
      { type: 'separator' },
      {
        label: 'Launch at Login',
        type:  'checkbox',
        checked: app.getLoginItemSettings().openAtLogin,
        click: (item) => {
          app.setLoginItemSettings({ openAtLogin: item.checked, openAsHidden: true });
          log(`Launch at login: ${item.checked}`);
          rebuild(); // refresh the checkmark
        },
      },
      { type: 'separator' },
      {
        label: 'Quit Spark',
        click: () => { isQuitting = true; app.quit(); },
      },
    ];
    tray.setContextMenu(Menu.buildFromTemplate(menuTemplate));
  };

  rebuild();
  tray.setToolTip('Spark — AI Desktop');

  tray.on('double-click', () => {
    if (!mainWindow) return;
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ─── Backend-ready callback ───────────────────────────────────────────────────

function onBackendReady(success) {
  if (success) {
    backendReady = true;
    log('Backend is ready — opening main window.');
    createMainWindow();
  } else {
    if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
    dialog.showMessageBox({
      type:      'error',
      title:     'Spark — Startup Timeout',
      message:   'The backend did not become ready within 60 seconds.',
      detail:    'Check logs/electron-backend.log for more information.',
      buttons:   ['View Logs', 'Retry', 'Quit'],
      defaultId: 1,
    }).then(({ response }) => {
      if (response === 0) shell.openPath(path.join(logDir, 'electron-backend.log'));
      if (response === 1) { createSplash(); startBackend(); pollBackend(onBackendReady); }
      if (response === 2) { isQuitting = true; app.quit(); }
    });
  }
}

// ─── Auto-Updater ──────────────────────────────────────────────────────────────

// Configure autoUpdater
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;

autoUpdater.on('checking-for-update', () => {
  log('Checking for update...');
});

autoUpdater.on('update-available', (info) => {
  log(`Update available: version ${info.version}`);
});

autoUpdater.on('update-not-available', () => {
  log('Update not available.');
});

autoUpdater.on('error', (err) => {
  log(`Auto-updater error: ${err.stack || err.message || err}`);
});

autoUpdater.on('download-progress', (progressObj) => {
  log(`Download progress: ${Math.round(progressObj.percent)}%`);
});

autoUpdater.on('update-downloaded', (info) => {
  log(`Update downloaded: version ${info.version}`);
  
  // Ask the user to restart now or later to install the update
  dialog.showMessageBox({
    type: 'info',
    title: 'Spark Update Ready',
    message: `A new version of Spark (${info.version}) has been downloaded.`,
    detail: 'Would you like to restart Spark now to apply the update?',
    buttons: ['Restart Now', 'Later'],
    defaultId: 0,
    cancelId: 1
  }).then(({ response }) => {
    if (response === 0) {
      isQuitting = true;
      autoUpdater.quitAndInstall();
    }
  });
});

function checkForUpdates() {
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify().catch(err => {
      log(`Auto-updater launch failed: ${err.message}`);
    });
  }
}

// ─── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  log('=== Spark Desktop starting ===');

  createTray();
  createSplash();

  // Check for updates on startup and every 2 hours
  checkForUpdates();
  setInterval(checkForUpdates, 2 * 60 * 60 * 1000);

  // Kill stale backend process on our port, then start fresh
  killPortIfBusy(PORT, () => {
    startBackend();
    pollBackend(onBackendReady);
  });
});

app.on('before-quit', () => {
  isQuitting = true;
  log('Quitting — shutting down backend…');
  if (backendProcess) {
    try { backendProcess.kill('SIGINT'); } catch (_) {}
  }
});

app.on('window-all-closed', () => {
  // On macOS it's conventional to stay active until the user explicitly quits.
  // On Windows/Linux we stay in the tray, so we intentionally do NOT call app.quit() here.
});

app.on('activate', () => {
  // macOS: re-open window when dock icon is clicked
  if (mainWindow) {
    mainWindow.show();
  } else if (backendReady) {
    createMainWindow();
  }
});

// ─── IPC: Custom window controls ─────────────────────────────────────────────

ipcMain.on('win:minimize', () => mainWindow?.minimize());
ipcMain.on('win:maximize', () => {
  if (!mainWindow) return;
  mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
});
ipcMain.on('win:close', () => mainWindow?.hide()); // hide to tray
ipcMain.on('win:control', (_event, action) => {
  if (!mainWindow) return;
  switch (action) {
    case 'minimize': mainWindow.minimize(); break;
    case 'maximize':
      mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
      break;
    case 'close':
    case 'hide':
      mainWindow.hide();
      break;
  }
});

// IPC: expose useful info to renderer
ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('app:serverUrl', () => SERVER_URL);
ipcMain.handle('app:isBackendReady', () => backendReady);

// ─── Glowing Screen Halo Window for Computer Control ──────────────────────────

let haloWindow = null;

function createHaloWindow() {
  if (haloWindow) return;

  const { screen } = require('electron');
  const primaryDisplay = screen.getPrimaryDisplay();

  haloWindow = new BrowserWindow({
    width: primaryDisplay.bounds.width,
    height: primaryDisplay.bounds.height,
    x: primaryDisplay.bounds.x,
    y: primaryDisplay.bounds.y,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: false,
    enableLargerThanScreen: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Enable click-through so user can interact with their screen normally
  haloWindow.setIgnoreMouseEvents(true);

  // Load a simple HTML string containing the glowing green border
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        html, body {
          margin: 0;
          padding: 0;
          width: 100%;
          height: 100%;
          overflow: hidden;
          background: transparent;
          box-sizing: border-box;
        }
        .halo-border {
          width: 100%;
          height: 100%;
          border: 6px solid #00ff41;
          box-shadow: inset 0 0 20px rgba(0, 255, 65, 0.6), 0 0 20px rgba(0, 255, 65, 0.6);
          box-sizing: border-box;
          animation: pulse 2s infinite alternate;
        }
        @keyframes pulse {
          0% { opacity: 0.7; box-shadow: inset 0 0 15px rgba(0, 255, 65, 0.4), 0 0 15px rgba(0, 255, 65, 0.4); }
          100% { opacity: 1.0; box-shadow: inset 0 0 30px rgba(0, 255, 65, 0.9), 0 0 30px rgba(0, 255, 65, 0.9); }
        }
      </style>
    </head>
    <body>
      <div class="halo-border"></div>
    </body>
    </html>
  `;

  haloWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);

  haloWindow.on('closed', () => {
    haloWindow = null;
  });
}

function destroyHaloWindow() {
  if (haloWindow) {
    haloWindow.close();
    haloWindow = null;
  }
}

ipcMain.on('halo:show', () => {
  createHaloWindow();
});

ipcMain.on('halo:hide', () => {
  destroyHaloWindow();
});

