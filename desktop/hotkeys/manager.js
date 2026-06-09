const { globalShortcut } = require('electron');

function setupHotkeys(mainWindow, voiceToggleCallback) {
  // Toggle main window on Ctrl+Alt+Space
  globalShortcut.register('Ctrl+Alt+Space', () => {
    if (mainWindow.isVisible()) {
      if (mainWindow.isFocused()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.focus();
      }
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  // Toggle voice mode on Ctrl+Shift+J
  globalShortcut.register('Ctrl+Shift+J', () => {
    if (voiceToggleCallback) {
      voiceToggleCallback();
    }
  });
}

function cleanUpHotkeys() {
  globalShortcut.unregisterAll();
}

module.exports = { setupHotkeys, cleanUpHotkeys };
