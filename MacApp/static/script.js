// 动态获取 API 基础地址：云端部署使用相对路径，本地开发使用当前主机
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://127.0.0.1:8000' 
    : '';

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentTranscript = ''; // 当前转写文本
let currentEventData = null; // 当前时间数据（可能是数组）
let currentEvents = []; // 当前多个事件数据（数组格式）
let isProgrammaticUpdate = false; // 标记是否是程序自动更新文本（而非用户手动编辑）
// DOM 元素
const recordBtn = document.getElementById('recordBtn');
const recordText = recordBtn.querySelector('.record-text');
const textArea = document.getElementById('textArea');
const transcriptText = document.getElementById('transcriptText');
const recentEventsArea = document.getElementById('recentEventsArea');
const recentEventsList = document.getElementById('recentEventsList');
const analyzeBtn = document.getElementById('analyzeBtn');
const undoBtn = document.getElementById('undoBtn');
const settingsBtn = document.getElementById('settingsBtn');
const statusArea = document.getElementById('statusArea');
const statusText = document.getElementById('statusText');
const analysisError = document.getElementById('analysisError');
const settingsModal = document.getElementById('settingsModal');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const tagsList = document.getElementById('tagsList');
const addTagBtn = document.getElementById('addTagBtn');

let operationStartTime = null; // 记录操作开始时间（用于计算用时）
let operationTranscribeMs = 0; // 仅语音转写耗时（不含写入日历）
let operationAnalyzeMs = 0;    // 仅 AI 分析耗时（不含写入日历）

function getSTTAndAnalysisSeconds() {
    const ms = (operationTranscribeMs || 0) + (operationAnalyzeMs || 0);
    if (ms > 0) return Math.round(ms / 1000);
    // 兜底：如果没采集到分段耗时，再退回原来的整体耗时
    return operationStartTime ? Math.round((Date.now() - operationStartTime) / 1000) : 0;
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    checkBackend();
    loadRecentEvents(); // 加载最近事件
    
    // 初始状态：隐藏"识别时间点"按钮
    analyzeBtn.classList.add('hidden');
});

// 检查后端是否运行
async function checkBackend() {
    try {
        const response = await fetch(`${API_BASE_URL}/`);
        if (!response.ok) {
            showStatus('后端未运行，请启动 app.py');
        }
    } catch (error) {
        showStatus('后端未运行，请启动 app.py');
    }
}

// 设置事件监听
function setupEventListeners() {
    // 录音按钮：按住录音（mousedown/touchstart 开始，mouseup/touchend 停止）
    recordBtn.addEventListener('mousedown', startRecordingOnHold);
    recordBtn.addEventListener('mouseup', stopRecordingOnHold);
    recordBtn.addEventListener('mouseleave', stopRecordingOnHold); // 鼠标移出也停止
    recordBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        startRecordingOnHold();
    });
    recordBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        stopRecordingOnHold();
    });
    
    // 文本框编辑：检测手动编辑，显示"识别时间点"按钮
    transcriptText.addEventListener('input', (e) => {
        currentTranscript = transcriptText.value;
        
        // 如果是程序自动更新，不显示按钮
        if (isProgrammaticUpdate) {
            isProgrammaticUpdate = false; // 重置标志
            return;
        }
        
        // 用户手动编辑时，隐藏之前的错误提示
        hideAnalysisError();
        
        // 用户手动编辑：显示按钮
        if (transcriptText.value.trim()) {
            analyzeBtn.classList.remove('hidden');
        } else {
            analyzeBtn.classList.add('hidden');
        }
    });
    
    // 监听鼠标点击和键盘输入，确保能检测到手动编辑
    transcriptText.addEventListener('focus', () => {
        // 当文本框获得焦点时，如果有文本且是手动编辑，显示按钮
        if (transcriptText.value.trim() && !isProgrammaticUpdate) {
            analyzeBtn.classList.remove('hidden');
        }
    });
    
    // 文本框回车键快速分析（Shift+Enter 换行）
    transcriptText.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (transcriptText.value.trim()) {
                analyzeTranscriptManual(transcriptText.value);
            }
        }
    });
    
    // 识别时间点按钮（支持直接输入文本后分析）
    analyzeBtn.addEventListener('click', () => {
        const text = transcriptText.value.trim();
        if (text) {
            // 先隐藏之前的错误提示
            hideAnalysisError();
            analyzeTranscriptManual(text);
        } else {
            showStatus('❌ 请输入文本或先录音');
        }
    });
    
    undoBtn.addEventListener('click', () => {
        undoLastEvents();
    });
    
    // 标签设置
    settingsBtn.addEventListener('click', () => {
        openSettingsModal();
    });
    
    closeSettingsBtn.addEventListener('click', () => {
        closeSettingsModal();
    });
    
    addTagBtn.addEventListener('click', () => {
        addNewTag();
    });
    
    // 点击模态框外部关闭
    settingsModal.addEventListener('click', (e) => {
        if (e.target === settingsModal) {
            closeSettingsModal();
        }
    });
    
    // Electron IPC - 按住录音模式
    if (window.electronAPI) {
        // 按住录音：开始
        window.electronAPI.onStartRecording(() => {
            if (!isRecording) {
                startRecording();
            }
        });
        
        // 按住录音：停止
        window.electronAPI.onStopRecording(() => {
            if (isRecording) {
                stopRecording();
            }
        });
        
        // 兼容旧的切换模式
        window.electronAPI.onToggleRecording(() => {
            toggleRecording();
        });
        
        window.electronAPI.onCalendarAdded((data) => {
            if (data.success) {
                const count = data.count || 1;
                const elapsedSeconds = getSTTAndAnalysisSeconds();
                showSuccessMessage(`🎉 记录成功！用时 ${elapsedSeconds} 秒（仅转写+分析）`);
                loadRecentEvents();
                resetUIAfterSuccess();
            } else {
                showStatus(`❌ 添加失败: ${data.error}`);
            }
        });
        
        // 监听全局键盘事件（用于检测快捷键松开）
        // 注意：Electron 的 globalShortcut 不支持 keyup，我们需要在页面中监听
        let shortcutKeys = { cmd: false, shift: false, t: false };
        
        document.addEventListener('keydown', (e) => {
            if (e.metaKey) shortcutKeys.cmd = true;
            if (e.shiftKey) shortcutKeys.shift = true;
            if (e.key.toLowerCase() === 't') shortcutKeys.t = true;
            
            // 检测是否按下了 Cmd+Shift+T
            if (shortcutKeys.cmd && shortcutKeys.shift && shortcutKeys.t) {
                if (window.electronAPI.notifyShortcutPressed) {
                    window.electronAPI.notifyShortcutPressed();
                }
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (e.metaKey) shortcutKeys.cmd = false;
            if (e.shiftKey) shortcutKeys.shift = false;
            if (e.key.toLowerCase() === 't') shortcutKeys.t = false;
            
            // 检测是否松开了 Cmd+Shift+T
            if (!shortcutKeys.cmd || !shortcutKeys.shift || !shortcutKeys.t) {
                if (window.electronAPI.notifyShortcutReleased) {
                    window.electronAPI.notifyShortcutReleased();
                }
            }
        });
    }
}

// 测试模式已移除，始终使用自动模式

// 按住录音：开始
async function startRecordingOnHold() {
    if (isRecording) return; // 防止重复触发
    await startRecording();
}

// 按住录音：停止
function stopRecordingOnHold() {
    if (!isRecording) return;
    stopRecording();
}

// 切换录音状态（保留用于快捷键）
async function toggleRecording() {
    if (!isRecording) {
        await startRecording();
    } else {
        stopRecording();
    }
}

// 检查可用的音频输入设备
async function checkAudioDevices() {
    try {
        // 先请求权限（这样才能枚举设备）
        await navigator.mediaDevices.getUserMedia({ audio: true });
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter(device => device.kind === 'audioinput');
        console.log('可用的音频输入设备:', audioInputs.map(d => d.label || d.deviceId));
        return audioInputs;
    } catch (error) {
        console.error('枚举设备失败:', error);
        // 如果权限被拒绝，返回空数组
        return [];
    }
}

// 开始录音
async function startRecording() {
    try {
        // 先检查可用设备（需要先请求权限）
        try {
            const audioDevices = await checkAudioDevices();
            if (audioDevices.length === 0) {
                showStatus('❌ 未找到麦克风设备\n\n请检查：\n1. 麦克风是否已连接\n2. 系统设置 → 声音 → 输入\n3. 确保选择了正确的输入设备');
                
                // 提供打开声音设置的选项
                setTimeout(() => {
                    if (confirm('未找到麦克风设备。是否打开声音设置检查输入设备？')) {
                        if (window.electronAPI && window.electronAPI.openSystemPreferences) {
                            window.electronAPI.openSystemPreferences('sound');
                        } else {
                            alert('请手动打开：系统设置 → 声音 → 输入\n检查麦克风是否已连接并选择');
                        }
                    }
                }, 1000);
                return;
            }
            console.log(`找到 ${audioDevices.length} 个音频输入设备`);
        } catch (deviceError) {
            console.warn('设备检查失败，继续尝试录音:', deviceError);
        }
        
        // 尝试获取麦克风权限并开始录音
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            } 
        });
        
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await processAudio(audioBlob);
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        // 注意：operationStartTime 不在录音开始时设置，而是在处理开始时设置（processAudio）
        // 这样只计算处理时间（STT + AI分析 + 写入日历），不包括录音时间
        recordBtn.classList.add('recording');
        recordText.textContent = '录音中...';
        showStatus('🎤 正在录音...');
        
        // 开始新录音时，隐藏之前的错误提示
        hideAnalysisError();
    } catch (error) {
        console.error('录音错误:', error);
        
        // 详细的错误提示
        let errorMessage = '❌ 无法访问麦克风';
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            errorMessage = '❌ 麦克风权限被拒绝\n请到系统设置 → 隐私与安全性 → 麦克风\n允许 Electron 应用访问麦克风';
        } else if (error.name === 'NotFoundError') {
            errorMessage = '❌ 未找到麦克风设备\n\n请检查：\n1. 麦克风是否已连接\n2. 系统设置 → 声音 → 输入\n3. 确保选择了正确的输入设备\n4. 尝试重新连接麦克风';
        } else if (error.name === 'NotReadableError') {
            errorMessage = '❌ 麦克风被其他应用占用\n请关闭其他使用麦克风的应用（如 Zoom、Teams 等）';
        } else {
            errorMessage = `❌ 录音错误: ${error.message || error.name}`;
        }
        
        showStatus(errorMessage);
        
        // 如果是权限问题，提供修复提示
        if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
            setTimeout(() => {
                if (confirm('需要授予麦克风权限。是否打开系统设置？')) {
                    // 打开系统设置到麦克风权限页面
                    if (window.electronAPI && window.electronAPI.openSystemPreferences) {
                        window.electronAPI.openSystemPreferences('microphone');
                    } else {
                        // 网页端：无法直接打开系统设置，显示提示
                        alert('请手动打开：系统设置 → 隐私与安全性 → 麦克风\n然后允许此网站访问麦克风');
                    }
                }
            }, 1000);
        } else if (error.name === 'NotFoundError') {
            // 如果是设备未找到，提供打开声音设置的选项
            setTimeout(() => {
                if (confirm('未找到麦克风设备。是否打开声音设置检查输入设备？')) {
                    if (window.electronAPI && window.electronAPI.openSystemPreferences) {
                        window.electronAPI.openSystemPreferences('sound');
                    } else {
                        alert('请手动打开：系统设置 → 声音 → 输入\n检查麦克风是否已连接并选择');
                    }
                }
            }, 1000);
        }
    }
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordText.textContent = '按住录音';
        showStatus('⏳ 处理中...');
    }
}

// 处理音频（自动模式）
async function processAudio(audioBlob) {
    // 在处理开始时记录时间（不包括录音时间）
    operationStartTime = Date.now();
    operationTranscribeMs = 0;
    operationAnalyzeMs = 0;
    
    try {
        // 1. 转录
        showStatus('📝 正在转录...');
        const transcribeStart = performance.now();
        const transcribeResult = await transcribeAudio(audioBlob);
        operationTranscribeMs = performance.now() - transcribeStart;
        
        // 处理返回结果（可能是对象或字符串）
        let transcript, model;
        if (typeof transcribeResult === 'string') {
            transcript = transcribeResult;
            model = '未知';
        } else {
            transcript = transcribeResult.transcript || transcribeResult.text || '';
            model = transcribeResult.model || transcribeResult.method || '未知';
        }
        
        console.log('转写结果:', { transcript, model, fullResult: transcribeResult });
        
        if (!transcript || transcript.trim() === '') {
            showStatus('❌ 转录失败：未获取到文本');
            return;
        }

        // 显示转写文本
        currentTranscript = transcript;
        // 程序自动填入转写文本，隐藏按钮
        isProgrammaticUpdate = true;
        transcriptText.value = transcript;
        analyzeBtn.classList.add('hidden');
        
        // 自动模式：继续分析
        await analyzeAndSave(transcript);
        
    } catch (error) {
        console.error('处理错误:', error);
        showStatus('❌ 处理失败: ' + (error.message || error));
    }
}

// 分析并保存（自动模式）
async function analyzeAndSave(transcript) {
    try {
        // 2. AI 分析
        showStatus('🤖 正在分析...');
        const analyzeStart = performance.now();
        const analysis = await analyzeTranscriptAPI(transcript);
        operationAnalyzeMs = performance.now() - analyzeStart;
        
        if (!analysis || !analysis.success) {
            showStatus('❌ 分析失败');
            showAnalysisError();
            return;
        }

        // 处理返回的数据（可能是数组或单个对象）
        const data = analysis.data;
        
        // 如果 data 是空数组或不存在，说明没有检测到有效的时间段
        if (!data || (Array.isArray(data) && data.length === 0)) {
            // 未检测出时间点，显示错误提示（不显示"分析失败"，因为分析是成功的，只是没有时间信息）
            showAnalysisError();
            hideStatus();
            return;
        }
        
        if (Array.isArray(data)) {
            currentEvents = data;
            currentEventData = data.length > 0 ? data[0] : null; // 兼容旧代码
        } else {
            currentEvents = [data];
            currentEventData = data;
        }
        
        // 检查是否检测到时间点（双重检查，确保安全）
        if (!currentEvents || currentEvents.length === 0) {
            // 未检测出时间点，显示错误提示
            showAnalysisError();
            hideStatus();
            return;
        }
        
        // 隐藏错误提示（如果有）
        hideAnalysisError();
        
        // 更新最近事件显示（分析完成后立即显示）
        displayRecentEvents(currentEvents);
        
        // 自动模式：直接写入日历
        await addToCalendar();
        
    } catch (error) {
        console.error('分析错误:', error);
        showStatus('❌ 分析失败: ' + (error.message || error));
        showAnalysisError();
    }
}

// 等待日历添加完成的 Promise 包装器（单个事件，保留兼容性）
function addToCalendarPromise() {
    return addMultipleToCalendarPromise([currentEventData]);
}

// 分析文本（测试模式手动调用）
async function analyzeTranscriptManual(transcript) {
    // 在处理开始时记录时间（手动分析模式）
    operationStartTime = Date.now();
    operationTranscribeMs = 0;
    operationAnalyzeMs = 0;
    
    try {
        showStatus('🤖 正在分析...');
        
        // 分析后隐藏按钮（等待下次手动编辑）
        analyzeBtn.classList.add('hidden');
        
        const analyzeStart = performance.now();
        const analysis = await analyzeTranscriptAPI(transcript);
        operationAnalyzeMs = performance.now() - analyzeStart;
        
        if (!analysis || !analysis.success) {
            showStatus('❌ 分析失败');
            return;
        }

        // 处理返回的数据（可能是数组或单个对象）
        const data = analysis.data;
        
        // 如果 data 是空数组或不存在，说明没有检测到有效的时间段
        if (!data || (Array.isArray(data) && data.length === 0)) {
            // 未检测出时间点，显示错误提示（不显示"分析失败"，因为分析是成功的，只是没有时间信息）
            showAnalysisError();
            hideStatus();
            return analysis;
        }
        
        if (Array.isArray(data)) {
            currentEvents = data;
            currentEventData = data.length > 0 ? data[0] : null; // 兼容旧代码
        } else {
            currentEvents = [data];
            currentEventData = data;
        }
        
        // 检查是否检测到时间点（双重检查，确保安全）
        if (!currentEvents || currentEvents.length === 0) {
            // 未检测出时间点，显示错误提示
            showAnalysisError();
            hideStatus();
            return analysis;
        }
        
        // 隐藏错误提示（如果有）
        hideAnalysisError();
        
        // 更新最近事件显示（分析完成后立即显示）
        displayRecentEvents(currentEvents);
        
        // 自动模式：直接写入日历
        await addToCalendar();
        
        return analysis;
    } catch (error) {
        console.error('分析错误:', error);
        showStatus('❌ 分析失败: ' + (error.message || error));
    }
}

// 转录音频
async function transcribeAudio(audioBlob) {
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.webm');
    formData.append('language', 'zh-CN');
    formData.append('use_local', 'true');

    try {
        const response = await fetch(`${API_BASE_URL}/api/transcribe`, {
            method: 'POST',
            body: formData,
            signal: AbortSignal.timeout(30000)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`转录失败 (${response.status}): ${errorText}`);
        }

        const result = await response.json();
        const transcript = result.transcript || result.text;
        
        if (!transcript) {
            throw new Error('转录结果为空');
        }
        
        // 返回完整结果，包括模型信息
        return {
            transcript: transcript,
            model: result.model || result.method || '未知',
            method: result.method || '未知',
            confidence: result.confidence
        };
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('转录超时（30秒）');
        }
        throw error;
    }
}

// 更新 STT 模型显示
// updateSTTModelDisplay 函数已移除，不再显示转写模型名称

// 分析文本 API
async function analyzeTranscriptAPI(transcript) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                transcript: transcript,
                use_ollama: true
            }),
            signal: AbortSignal.timeout(60000)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`分析失败 (${response.status}): ${errorText}`);
        }

        return await response.json();
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('分析超时（60秒）');
        }
        throw error;
    }
}

// 这些函数已不再使用（保留用于兼容）
function displayTimeData(data) {
    // 已移除，现在使用 displayRecentEvents
}

function displayTimeDataMultiple(events) {
    // 已移除，现在使用 displayRecentEvents
    displayRecentEvents(events);
}

// 格式化日期时间
function formatDateTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// 添加到日历（支持多个事件）
async function addToCalendar() {
    if (!currentEvents || currentEvents.length === 0) {
        showStatus('❌ 没有可添加的数据');
        return;
    }
    
    try {
        const count = currentEvents.length;
        showStatus(`📅 正在添加 ${count} 个事件到日历...`);
        
        let result;
        if (window.electronAPI) {
            // Electron 模式：通过 IPC 批量添加
            result = await addMultipleToCalendarPromise(currentEvents);
        } else {
            // 网页端：使用 API 批量添加
            result = await addMultipleToCalendarAPI(currentEvents);
        }
        
        if (result && result.success) {
            // 仅统计：语音转写 + AI 分析（不包含写入日历耗时）
            const elapsedSeconds = getSTTAndAnalysisSeconds();
            
            // 显示成功提示（底部弹出）
            showSuccessMessage(`🎉 记录成功！用时 ${elapsedSeconds} 秒（仅转写+分析）`);
            
            // 重新加载最近事件（显示刚写入的事件）
            await loadRecentEvents();
            
            // 重置 UI（但保留最近事件显示）
            resetUIAfterSuccess();
        } else {
            throw new Error(result?.error || '添加失败');
        }
    } catch (error) {
        console.error('添加到日历错误:', error);
        showStatus('❌ 添加失败: ' + (error.message || error));
    }
}

// 通过 API 批量添加到日历
async function addMultipleToCalendarAPI(events) {
    try {
        // 加载标签配置以获取颜色
        let tagsMap = {};
        try {
            const tagsResponse = await fetch(`${API_BASE_URL}/api/tags`, {
                signal: AbortSignal.timeout(3000)
            });
            if (tagsResponse.ok) {
                const tagsResult = await tagsResponse.json();
                if (tagsResult.success) {
                    tagsResult.tags.forEach(tag => {
                        tagsMap[tag.name] = tag.color || '#95E1D3';
                    });
                }
            }
        } catch (error) {
            console.warn('加载标签配置失败:', error);
        }
        
        // 转换事件格式，使用 tag 作为 calendar_name
        const calendarEvents = events.map(event => {
            const tag = event.tag || '生活';
            const tagColor = tagsMap[tag] || '#95E1D3';
            return {
                activity: event.activity,
                start_time: event.start_time,
                end_time: event.end_time,
                description: event.description || '',
                location: event.location || '',
                calendar_name: tag,  // 使用 tag 作为日历名称（标签）
                tag: tag,  // 保存 tag 字段用于前端显示
                tag_color: tagColor,  // 传递标签颜色给后端
                recurrence: event.recurrence || null
            };
        });
        
        const response = await fetch(`${API_BASE_URL}/api/calendar/add-multiple`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(calendarEvents),
            signal: AbortSignal.timeout(30000)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`添加失败 (${response.status}): ${errorText}`);
        }

        const result = await response.json();
        if (!result.success) {
            throw new Error(result.error || '添加失败');
        }
        
        return result;
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('添加超时（30秒）');
        }
        throw error;
    }
}

// 等待多个事件添加到日历完成的 Promise 包装器（Electron）
// 注意：Electron 模式下，我们通过 API 批量添加，而不是逐个添加
function addMultipleToCalendarPromise(events) {
    // Electron 模式下，直接调用 API 批量添加
    return addMultipleToCalendarAPI(events);
}

// 撤回最近写入的事件
async function undoLastEvents() {
    try {
        showStatus('🔄 正在撤回...');
        
        const response = await fetch(`${API_BASE_URL}/api/calendar/undo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            signal: AbortSignal.timeout(10000)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`撤回失败 (${response.status}): ${errorText}`);
        }

        const result = await response.json();
        
        // 显示每个事件的撤回结果
        if (result.results && result.results.length > 0) {
            const messages = result.results.map(r => {
                const activity = r.activity || '未命名活动';
                if (r.success) {
                    return `✅ "${activity}" 撤回成功`;
                } else {
                    // 优化错误消息显示
                    let errorMsg = r.error || '未知错误';
                    // 简化错误消息（移除技术细节）
                    if (errorMsg.includes('-1728') || errorMsg.includes("Can't get event")) {
                        errorMsg = '事件不存在（可能已被手动删除）';
                    } else if (errorMsg.length > 50) {
                        // 如果错误消息太长，只显示关键部分
                        errorMsg = errorMsg.substring(0, 50) + '...';
                    }
                    return `❌ "${activity}" 撤回失败：${errorMsg}`;
                }
            });
            
            // 显示所有结果（每个事件一行）
            showStatus(messages.join('\n'));
            
            // 如果至少有一个成功，重新加载最近事件
            if (result.deleted_count > 0) {
                await loadRecentEvents();
            }
            // 即使全部失败，也不抛出异常，而是显示详细结果
        } else if (result.success) {
            // 兼容旧格式（没有 results 字段）
            const count = result.deleted_count || 1;
            showStatus(`✅ 已撤回 ${count} 个事件`);
            await loadRecentEvents();
        } else {
            // 只有在完全没有结果数据时才抛出异常
            throw new Error(result.error || '撤回失败');
        }
        
        // 5秒后自动隐藏（因为可能有多行消息）
        setTimeout(() => {
            hideStatus();
        }, 5000);
    } catch (error) {
        console.error('撤回错误:', error);
        showStatus('❌ 撤回失败: ' + (error.message || error));
    }
}

// 显示状态
function showStatus(text) {
    statusText.textContent = text;
    statusArea.classList.remove('hidden');
}

// 隐藏状态
function hideStatus() {
    statusArea.classList.add('hidden');
}

// 重置 UI
// 重置 UI（写入成功后调用，保留转写文本框和最近事件显示）
function resetUIAfterSuccess() {
    // 不清空转写文本框，不清空最近事件
    // 只重置当前操作相关的变量
    currentEventData = null;
    currentEvents = [];
    operationStartTime = null;
    // 不隐藏状态提示（让成功消息显示）
}

// 完全重置 UI（保留用于其他场景）
function resetUI() {
    resetUIAfterSuccess();
    hideStatus();
}

// 加载最近事件
async function loadRecentEvents() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/calendar/recent`, {
            method: 'GET',
            signal: AbortSignal.timeout(5000)
        });

        if (!response.ok) {
            throw new Error(`获取最近事件失败 (${response.status})`);
        }

        const result = await response.json();
        if (result.success && result.events && result.events.length > 0) {
            displayRecentEvents(result.events);
            undoBtn.classList.remove('hidden');
        } else {
            displayRecentEvents([]);
            undoBtn.classList.add('hidden');
        }
    } catch (error) {
        console.error('加载最近事件错误:', error);
        displayRecentEvents([]);
    }
}

// 显示最近事件（带标签和颜色）
async function displayRecentEvents(events) {
    if (!events || events.length === 0) {
        recentEventsList.innerHTML = '<div class="recent-event-placeholder">暂无最近事件</div>';
        undoBtn.classList.add('hidden');
        return;
    }
    
    undoBtn.classList.remove('hidden');
    
    // 加载标签配置（获取颜色）
    let tagsMap = {};
    try {
        const tagsResponse = await fetch(`${API_BASE_URL}/api/tags`, {
            signal: AbortSignal.timeout(3000)
        });
        if (tagsResponse.ok) {
            const tagsResult = await tagsResponse.json();
            if (tagsResult.success) {
                tagsResult.tags.forEach(tag => {
                    tagsMap[tag.name] = tag.color || '#95E1D3';
                });
            }
        }
    } catch (error) {
        console.warn('加载标签配置失败:', error);
    }
    
    const html = events.map(event => {
        const startTime = event.start_time ? formatDateTime(event.start_time) : '-';
        const endTime = event.end_time ? formatDateTime(event.end_time) : '-';
        const activity = event.activity || '未命名活动';
        const tag = event.tag || '生活';
        const tagColor = tagsMap[tag] || '#95E1D3';
        
        return `
            <div class="recent-event-item">
                <div class="recent-event-header">
                    <div class="recent-event-activity">${activity}</div>
                    <span class="recent-event-tag" style="background-color: ${tagColor}">${tag}</span>
                </div>
                <div class="recent-event-time">${startTime} - ${endTime}</div>
            </div>
        `;
    }).join('');
    
    recentEventsList.innerHTML = html;
}

// 显示成功消息（底部弹出）
function showSuccessMessage(message) {
    statusText.textContent = message;
    statusArea.classList.remove('hidden');
    statusArea.classList.add('success-message');
    
    // 3秒后自动隐藏
    setTimeout(() => {
        statusArea.classList.remove('success-message');
        hideStatus();
    }, 3000);
}

// 显示分析错误（未检测出时间点）
function showAnalysisError() {
    if (analysisError) {
        analysisError.classList.remove('hidden');
    }
}

// 隐藏分析错误
function hideAnalysisError() {
    if (analysisError) {
        analysisError.classList.add('hidden');
    }
}

// ========== 标签设置功能 ==========

// 打开设置弹窗
async function openSettingsModal() {
    settingsModal.classList.remove('hidden');
    await loadTags();
}

// 关闭设置弹窗
function closeSettingsModal() {
    settingsModal.classList.add('hidden');
}

// 加载标签列表
async function loadTags() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/tags`, {
            signal: AbortSignal.timeout(5000)
        });
        
        if (!response.ok) {
            throw new Error(`获取标签失败 (${response.status})`);
        }
        
        const result = await response.json();
        if (result.success) {
            displayTags(result.tags);
        } else {
            showStatus('❌ 加载标签失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('加载标签错误:', error);
        showStatus('❌ 加载标签失败: ' + (error.message || error));
    }
}

// 显示标签列表
function displayTags(tags) {
    if (!tags || tags.length === 0) {
        tagsList.innerHTML = '<div class="no-tags">暂无标签</div>';
        return;
    }
    
    const html = tags.map(tag => {
        const isDefault = tag.is_default || false;
        
        return `
            <div class="tag-item" data-tag-id="${tag.id}">
                <div class="tag-color-preview" style="background-color: ${tag.color || '#95E1D3'}"></div>
                <div class="tag-content">
                    <div class="tag-name-row">
                        <input type="text" class="tag-name-input" value="${escapeHtml(tag.name)}" data-field="name">
                        ${isDefault ? '<span class="tag-default-badge">默认</span>' : ''}
                        <button class="tag-delete-btn" onclick="deleteTag('${tag.id}')">删除</button>
                    </div>
                    <input type="text" class="tag-desc-input" value="${escapeHtml(tag.description || '')}" placeholder="标签描述（用于 LLM 分类）" data-field="description">
                    <div class="tag-color-row">
                        <label>颜色：</label>
                        <input type="color" class="tag-color-input" value="${tag.color || '#95E1D3'}" data-field="color">
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    tagsList.innerHTML = html;
    
    // 绑定输入事件（自动保存）
    tagsList.querySelectorAll('.tag-name-input, .tag-desc-input, .tag-color-input').forEach(input => {
        let saveTimeout;
        input.addEventListener('input', () => {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                const tagItem = input.closest('.tag-item');
                const tagId = tagItem.dataset.tagId;
                saveTag(tagId, tagItem);
            }, 1000); // 1秒后自动保存
        });
    });
}

// 转义HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 保存标签（更新）
async function saveTag(tagId, tagItem) {
    const nameInput = tagItem.querySelector('.tag-name-input');
    const descInput = tagItem.querySelector('.tag-desc-input');
    const colorInput = tagItem.querySelector('.tag-color-input');
    
    const tagData = {
        name: nameInput.value.trim(),
        description: descInput.value.trim(),
        color: colorInput.value
    };
    
    if (!tagData.name) {
        showStatus('❌ 标签名称不能为空');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/tags/${tagId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tagData),
            signal: AbortSignal.timeout(5000)
        });
        
        const result = await response.json();
        if (result.success) {
            // 静默保存成功，不显示提示
            console.log('标签已保存:', tagData.name);
        } else {
            showStatus('❌ 保存失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('保存标签错误:', error);
        showStatus('❌ 保存失败: ' + (error.message || error));
    }
}

// 删除标签
async function deleteTag(tagId) {
    if (!confirm('确定要删除这个标签吗？')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/tags/${tagId}`, {
            method: 'DELETE',
            signal: AbortSignal.timeout(5000)
        });
        
        const result = await response.json();
        if (result.success) {
            showStatus('✅ ' + (result.message || '标签已删除'));
            await loadTags(); // 重新加载标签列表
        } else {
            showStatus('❌ 删除失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('删除标签错误:', error);
        showStatus('❌ 删除失败: ' + (error.message || error));
    }
}

// 添加新标签
function addNewTag() {
    const newTagHtml = `
        <div class="tag-item tag-item-new" data-tag-id="new">
            <div class="tag-color-preview" style="background-color: #95E1D3"></div>
            <div class="tag-content">
                <div class="tag-name-row">
                    <input type="text" class="tag-name-input" placeholder="标签名称" data-field="name">
                    <button class="tag-save-btn" onclick="saveNewTag(this)">保存</button>
                    <button class="tag-cancel-btn" onclick="cancelNewTag(this)">取消</button>
                </div>
                <input type="text" class="tag-desc-input" placeholder="标签描述（用于 LLM 分类）" data-field="description">
                <div class="tag-color-row">
                    <label>颜色：</label>
                    <input type="color" class="tag-color-input" value="#95E1D3" data-field="color">
                </div>
            </div>
        </div>
    `;
    
    tagsList.insertAdjacentHTML('beforeend', newTagHtml);
    
    // 滚动到新标签
    const newTagItem = tagsList.querySelector('.tag-item-new');
    newTagItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    newTagItem.querySelector('.tag-name-input').focus();
}

// 保存新标签
async function saveNewTag(button) {
    const tagItem = button.closest('.tag-item');
    const nameInput = tagItem.querySelector('.tag-name-input');
    const descInput = tagItem.querySelector('.tag-desc-input');
    const colorInput = tagItem.querySelector('.tag-color-input');
    
    const tagData = {
        name: nameInput.value.trim(),
        description: descInput.value.trim(),
        color: colorInput.value
    };
    
    if (!tagData.name) {
        showStatus('❌ 标签名称不能为空');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tagData),
            signal: AbortSignal.timeout(5000)
        });
        
        const result = await response.json();
        if (result.success) {
            showStatus('✅ 标签已创建');
            await loadTags(); // 重新加载标签列表
        } else {
            showStatus('❌ 创建失败: ' + (result.error || '未知错误'));
        }
    } catch (error) {
        console.error('创建标签错误:', error);
        showStatus('❌ 创建失败: ' + (error.message || error));
    }
}

// 取消添加新标签
function cancelNewTag(button) {
    const tagItem = button.closest('.tag-item-new');
    tagItem.remove();
}
