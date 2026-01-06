const { contextBridge, ipcRenderer } = require('electron');

let calendarAddedHandler = null;

contextBridge.exposeInMainWorld('electronAPI', {
  toggleRecording: () => ipcRenderer.send('toggle-recording'),
  onToggleRecording: (callback) => {
    ipcRenderer.on('toggle-recording', callback);
  },
  // 按住录音：开始
  onStartRecording: (callback) => {
    ipcRenderer.on('start-recording', callback);
  },
  // 按住录音：停止
  onStopRecording: (callback) => {
    ipcRenderer.on('stop-recording', callback);
  },
  // 通知主进程快捷键状态
  notifyShortcutPressed: () => ipcRenderer.send('shortcut-pressed'),
  notifyShortcutReleased: () => ipcRenderer.send('shortcut-released'),
  // 打开系统设置
  openSystemPreferences: (pane) => ipcRenderer.invoke('open-system-preferences', pane),
  addToCalendar: (eventData) => ipcRenderer.send('add-to-calendar', eventData),
  onCalendarAdded: (callback) => {
    // 移除之前的监听器
    if (calendarAddedHandler) {
      ipcRenderer.removeListener('calendar-added', calendarAddedHandler);
    }
    
    if (callback) {
      calendarAddedHandler = (event, data) => callback(data);
      ipcRenderer.on('calendar-added', calendarAddedHandler);
    } else {
      // 如果 callback 为 null，移除监听器
      if (calendarAddedHandler) {
        ipcRenderer.removeListener('calendar-added', calendarAddedHandler);
        calendarAddedHandler = null;
      }
    }
  }
});

