const { app, BrowserWindow, globalShortcut, Tray, Menu, ipcMain, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, exec } = require('child_process');

let mainWindow;
let tray;
let isRecording = false;
let pythonBackend;

// 检查后端是否已运行
function checkBackendRunning() {
  return new Promise((resolve) => {
    exec('lsof -ti:8000', (error, stdout) => {
      resolve(stdout.trim().length > 0);
    });
  });
}

// 启动 Python 后端
async function startBackend() {
  // 先检查后端是否已运行
  const isRunning = await checkBackendRunning();
  if (isRunning) {
    console.log('后端已在运行，跳过启动');
    return;
  }

  const backendPath = path.join(__dirname, '..', 'app.py');
  pythonBackend = spawn('python3', [backendPath], {
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit'
  });

  pythonBackend.on('error', (err) => {
    console.error('Failed to start backend:', err);
  });

  pythonBackend.on('exit', (code) => {
    if (code !== 0 && code !== null) {
      console.log(`Backend exited with code ${code}`);
      // 如果是因为端口占用退出，不报错（后端可能已在运行）
      if (code === 1) {
        console.log('可能是端口被占用，后端可能已在运行');
      }
    }
  });
}

// 创建系统托盘
function createTray() {
  const iconPath = path.join(__dirname, 'icon.png');
  let trayIcon = nativeImage.createEmpty();
  
  // 如果没有图标，创建一个简单的图标
  if (!trayIcon.isEmpty()) {
    tray = new Tray(trayIcon);
  } else {
    // 使用默认图标
    tray = new Tray(nativeImage.createEmpty());
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '开始录音',
      click: () => {
        if (mainWindow) {
          mainWindow.webContents.send('toggle-recording');
        }
      }
    },
    {
      label: '显示窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.quit();
      }
    }
  ]);

  tray.setToolTip('TimeFlow Calendar');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
    }
  });
}

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 320,
    height: 500,
    frame: true,
    resizable: true,
    alwaysOnTop: false,
    movable: true, // 允许拖动
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#ffffff'
  });

  mainWindow.loadFile(path.join(__dirname, 'static', 'index.html'));

  // 窗口关闭时隐藏到托盘
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      // 窗口隐藏时取消快捷键注册
      unregisterGlobalShortcut();
    }
  });

  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
    // 窗口隐藏时取消快捷键注册
    unregisterGlobalShortcut();
  });
  
  // 窗口显示时注册快捷键
  mainWindow.on('show', () => {
    registerGlobalShortcut();
  });
  
  // 窗口隐藏时取消快捷键
  mainWindow.on('hide', () => {
    unregisterGlobalShortcut();
  });
  
  // 窗口聚焦时注册快捷键（确保只在应用激活时响应）
  mainWindow.on('focus', () => {
    registerGlobalShortcut();
  });
  
  // 窗口失焦时取消快捷键（避免与其他应用冲突）
  mainWindow.on('blur', () => {
    unregisterGlobalShortcut();
    isShortcutPressed = false; // 重置状态
  });
}

// 注册全局快捷键（只在窗口可见且聚焦时注册）
let isShortcutPressed = false;

function registerGlobalShortcut() {
  // 先取消所有已注册的快捷键，避免冲突
  globalShortcut.unregisterAll();
  
  // 注册快捷键按下事件
  const ret = globalShortcut.register('CommandOrControl+Shift+T', () => {
    // 只在窗口可见且聚焦时才响应快捷键
    if (mainWindow && mainWindow.isVisible() && mainWindow.isFocused() && !isShortcutPressed) {
      isShortcutPressed = true;
      mainWindow.webContents.send('start-recording');
      // 通知前端快捷键已按下
      if (mainWindow.webContents) {
        mainWindow.webContents.executeJavaScript(`
          if (window.electronAPI && window.electronAPI.notifyShortcutPressed) {
            window.electronAPI.notifyShortcutPressed();
          }
        `);
      }
    }
  });

  if (!ret) {
    console.log('⚠️ 快捷键注册失败，可能已被其他应用占用（如 Cursor）');
    console.log('💡 提示：请关闭 Cursor 或其他应用的 Cmd+Shift+T 快捷键');
    console.log('💡 或者：只在应用窗口打开时使用快捷键（窗口聚焦时自动注册）');
  } else {
    console.log('✅ 全局快捷键已注册（仅在窗口可见且聚焦时生效）');
  }
}

// 取消全局快捷键
function unregisterGlobalShortcut() {
  globalShortcut.unregister('CommandOrControl+Shift+T');
  console.log('✅ 全局快捷键已取消注册');
}

// 添加到苹果日历（使用 AppleScript）
function addToCalendar(eventData) {
  return new Promise((resolve, reject) => {
    const { activity, start_time, end_time, description, status } = eventData;
    
    // 转义特殊字符
    const escapeAppleScript = (str) => {
      if (!str) return '';
      return str.replace(/\\/g, '\\\\')
                 .replace(/"/g, '\\"')
                 .replace(/\n/g, '\\n');
    };
    
    // 格式化日期时间
    const startDate = new Date(start_time);
    const endDate = new Date(end_time);
    
    // 计算从当前时间到目标时间的秒数差（用于 AppleScript）
    const getSecondsFromNow = (targetDate) => {
      const now = new Date();
      const diffMs = targetDate.getTime() - now.getTime();
      return Math.round(diffMs / 1000); // 转换为秒
    };

    const escapedActivity = escapeAppleScript(activity || '未命名活动');
    // description 优先，如果没有则使用 status
    const descText = description || (status ? `状态: ${status}` : '');
    const escapedDescription = escapeAppleScript(descText);

    // 使用多个 -e 参数执行 AppleScript（避免多行字符串问题）
    const { exec } = require('child_process');
    const startSeconds = getSecondsFromNow(startDate);
    const endSeconds = getSecondsFromNow(endDate);
    
    // 构建命令：使用多个 -e 参数
    const commands = [
      'tell application "Calendar"',
      'activate',
      'set calendarName to "TimeFlow"',
      'try',
      'set targetCalendar to calendar calendarName',
      'on error',
      'make new calendar with properties {name:calendarName}',
      'set targetCalendar to calendar calendarName',
      'end try',
      'tell targetCalendar',
      `make new event at end with properties {summary:"${escapedActivity}", start date:(current date) + ${startSeconds}, end date:(current date) + ${endSeconds}, description:"${escapedDescription}"}`,
      'end tell',
      'return "success"',
      'end tell'
    ];
    
    const cmd = `osascript ${commands.map(c => `-e '${c.replace(/'/g, "'\\''")}'`).join(' ')}`;
    
    exec(cmd, { encoding: 'utf8' }, (error, stdout, stderr) => {
      if (error) {
        console.error('AppleScript 错误:', error);
        console.error('stderr:', stderr);
        reject(error);
      } else {
        console.log('已添加到日历:', stdout);
        resolve(stdout);
      }
    });
  });
}

// IPC 通信
ipcMain.on('toggle-recording', () => {
  if (mainWindow) {
    mainWindow.webContents.send('toggle-recording');
  }
});

// 监听快捷键状态更新（从前端发送）
ipcMain.on('shortcut-pressed', () => {
  isShortcutPressed = true;
});

ipcMain.on('shortcut-released', () => {
  isShortcutPressed = false;
  if (mainWindow && mainWindow.isVisible()) {
    mainWindow.webContents.send('stop-recording');
  }
});

ipcMain.on('add-to-calendar', async (event, eventData) => {
  try {
    await addToCalendar(eventData);
    event.reply('calendar-added', { success: true, count: 1 });
  } catch (error) {
    event.reply('calendar-added', { success: false, error: error.message });
  }
});

// 打开系统设置
ipcMain.handle('open-system-preferences', async (event, pane) => {
  const { exec } = require('child_process');
  return new Promise((resolve, reject) => {
    let url;
    switch (pane) {
      case 'microphone':
        url = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone';
        break;
      case 'accessibility':
        url = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility';
        break;
      case 'sound':
      case 'audio':
        url = 'x-apple.systempreferences:com.apple.preference.sound?Input';
        break;
      default:
        url = 'x-apple.systempreferences:com.apple.preference.security';
    }
    
    exec(`open "${url}"`, (error) => {
      if (error) {
        reject(error);
      } else {
        resolve(true);
      }
    });
  });
});

// 应用启动
app.whenReady().then(() => {
  startBackend();
  createWindow();
  createTray();
  registerGlobalShortcut();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else if (mainWindow) {
      mainWindow.show();
    }
  });
});

// 应用退出
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (pythonBackend) {
    pythonBackend.kill();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

