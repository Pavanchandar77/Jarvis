const fs = require('fs');
const path = require('path');
const { app } = require('electron');

const AUTOSTART_DIR = path.join(app.getPath('home'), '.config/autostart');
const DESKTOP_FILE_PATH = path.join(AUTOSTART_DIR, 'jarvis.desktop');

function setupAutostart() {
  try {
    if (!fs.existsSync(AUTOSTART_DIR)) {
      fs.mkdirSync(AUTOSTART_DIR, { recursive: true });
    }

    let execPath = process.execPath;
    const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;
    if (isDev) {
      const projectPath = path.resolve(__dirname, '..');
      execPath = `"${execPath}" "${projectPath}" --hidden`;
    } else {
      execPath = `"${execPath}" --hidden`;
    }

    const iconPath = path.join(__dirname, '../../assets/OpenJarvis_Circular_Logo.png');

    const desktopFileContent = `[Desktop Entry]
Type=Application
Version=1.0
Name=Jarvis OS
Comment=J.A.R.V.I.S. Persistent Ambient Runtime
Exec=${execPath}
Icon=${iconPath}
Terminal=false
Categories=Utility;Development;
StartupNotify=false
X-GNOME-Autostart-enabled=true
`;

    fs.writeFileSync(DESKTOP_FILE_PATH, desktopFileContent, { encoding: 'utf-8', mode: 0o755 });
    return true;
  } catch (err) {
    console.error('Failed to setup autostart:', err);
    return false;
  }
}

function removeAutostart() {
  try {
    if (fs.existsSync(DESKTOP_FILE_PATH)) {
      fs.unlinkSync(DESKTOP_FILE_PATH);
      return true;
    }
  } catch (err) {
    console.error('Failed to remove autostart:', err);
  }
  return false;
}

module.exports = { setupAutostart, removeAutostart };
