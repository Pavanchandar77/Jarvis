const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Maps common shortcut app names to Linux CLI executable commands.
 */
const APP_COMMANDS = {
  chrome: 'google-chrome',
  firefox: 'firefox',
  vscode: 'code',
  cursor: 'cursor',
  terminal: 'gnome-terminal',
  calculator: 'gnome-calculator',
  files: 'nautilus'
};

function setupBridge(ipcMain) {
  // SECURE OS APP LAUNCHER
  ipcMain.handle('os:open-app', async (event, appName) => {
    const cleanName = appName.trim().toLowerCase();
    const command = APP_COMMANDS[cleanName] || cleanName;
    
    // Simple sanitization to prevent malicious injection
    if (/[;&|`$]/.test(command)) {
      return { success: false, error: 'Access Denied: Invalid characters in command' };
    }
    
    return new Promise((resolve) => {
      exec(command, (error) => {
        if (error) {
          resolve({ success: false, error: error.message });
        } else {
          resolve({ success: true });
        }
      });
    });
  });

  // SECURE NATIVE DIRECTORY OPENER
  ipcMain.handle('os:open-folder', async (event, folderPath) => {
    // Resolve relative path to ensure absolute
    const resolvedPath = path.resolve(folderPath);
    
    if (!fs.existsSync(resolvedPath)) {
      return { success: false, error: 'Directory does not exist' };
    }
    
    return new Promise((resolve) => {
      exec(`xdg-open "${resolvedPath}"`, (error) => {
        if (error) {
          resolve({ success: false, error: error.message });
        } else {
          resolve({ success: true });
        }
      });
    });
  });

  // SECURE FILE OPENER
  ipcMain.handle('os:open-file', async (event, filePath) => {
    const resolvedPath = path.resolve(filePath);
    
    if (!fs.existsSync(resolvedPath)) {
      return { success: false, error: 'File does not exist' };
    }
    
    return new Promise((resolve) => {
      exec(`xdg-open "${resolvedPath}"`, (error) => {
        if (error) {
          resolve({ success: false, error: error.message });
        } else {
          resolve({ success: true });
        }
      });
    });
  });
}

module.exports = { setupBridge };
