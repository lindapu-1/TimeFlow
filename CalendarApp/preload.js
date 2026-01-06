const { contextBridge, ipcRenderer } = require('electron');

let calendarAddedHandler = null;

contextBridge.exposeInMainWorld('electronAPI', {
  toggleRecording: () => ipcRenderer.send('toggle-recording'),
  onToggleRecording: (callback) => {
    ipcRenderer.on('toggle-recording', callback);
  },
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

