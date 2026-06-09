const { Menu, Tray, app } = require('electron');
const path = require('path');

let tray = null;

function setupTray(mainWindow, hudWindow, { onVoiceToggle, onApproveTask, onHUDToggle }) {
  const iconPath = path.join(__dirname, '../../assets/OpenJarvis_Circular_Logo.png');
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    { label: 'J.A.R.V.I.S. Core', enabled: false },
    { type: 'separator' },
    { label: 'Status: Standby', id: 'status-item', enabled: false },
    { label: 'Objective: None', id: 'objective-item', enabled: false },
    { type: 'separator' },
    { label: 'Quick Approve Step', id: 'approve-item', enabled: false, click: () => { if (onApproveTask) onApproveTask(); } },
    { label: 'Toggle Voice Mode (Ctrl+Shift+J)', click: () => { if (onVoiceToggle) onVoiceToggle(); } },
    { label: 'Toggle HUD Overlay', click: () => { if (onHUDToggle) onHUDToggle(); } },
    { type: 'separator' },
    { label: 'Show Main Window', click: () => { mainWindow.show(); mainWindow.focus(); } },
    { label: 'Hide Main Window', click: () => { mainWindow.hide(); } },
    { type: 'separator' },
    { label: 'Quit J.A.R.V.I.S.', click: () => { app.quit(); } }
  ]);

  tray.setToolTip('J.A.R.V.I.S. OS Mode');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  return tray;
}

function updateTrayStatus(status, objective, approvalAwaiting) {
  if (!tray) return;
  const menu = tray.getContextMenu();
  if (!menu) return;

  const statusItem = menu.items.find(item => item.id === 'status-item');
  if (statusItem) {
    statusItem.label = `Status: ${status}`;
  }

  const objectiveItem = menu.items.find(item => item.id === 'objective-item');
  if (objectiveItem) {
    objectiveItem.label = `Objective: ${objective || 'None'}`;
  }

  const approveItem = menu.items.find(item => item.id === 'approve-item');
  if (approveItem) {
    approveItem.enabled = !!approvalAwaiting;
  }

  tray.setContextMenu(menu);
}

module.exports = { setupTray, updateTrayStatus };
