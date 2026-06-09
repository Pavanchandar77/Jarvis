const { Notification } = require('electron');
const path = require('path');

function setupNotifications(ipcMain) {
  ipcMain.on('os:show-notification', (event, { title, body }) => {
    sendLocalNotification(title, body);
  });
}

function sendLocalNotification(title, body) {
  if (Notification.isSupported()) {
    const notification = new Notification({
      title: title || 'J.A.R.V.I.S. Alert',
      body: body || '',
      icon: path.join(__dirname, '../../assets/OpenJarvis_Circular_Logo.png'),
      silent: false
    });
    notification.show();
  }
}

module.exports = { setupNotifications, sendLocalNotification };
