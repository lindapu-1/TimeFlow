const API_BASE_URL = 'http://127.0.0.1:8000';

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let testMode = false; // 测试模式开关
let currentTranscript = ''; // 当前转写文本
let currentEventData = null; // 当前时间数据（可能是数组）
let currentEvents = []; // 当前多个事件数据（数组格式）
let currentSTTModel = ''; // 当前使用的 STT 模型

// DOM 元素
const testModeBtn = document.getElementById('testModeBtn');
const recordBtn = document.getElementById('recordBtn');
const recordText = recordBtn.querySelector('.record-text');
const textArea = document.getElementById('textArea');
const transcriptText = document.getElementById('transcriptText');
const timeDataArea = document.getElementById('timeDataArea');
const dataActivity = document.getElementById('dataActivity');
const dataStartTime = document.getElementById('dataStartTime');
const dataEndTime = document.getElementById('dataEndTime');
const dataDescription = document.getElementById('dataDescription');
const manualActions = document.getElementById('manualActions');
const analyzeBtn = document.getElementById('analyzeBtn');
const confirmBtn = document.getElementById('confirmBtn');
const undoBtn = document.getElementById('undoBtn');
const statusArea = document.getElementById('statusArea');
const statusText = document.getElementById('statusText');
const sttModelInfo = document.getElementById('sttModelInfo');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('页面加载完成，sttModelInfo 元素:', sttModelInfo);
    setupEventListeners();
    checkBackend();
    loadTestMode();
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
    // 测试模式切换
    testModeBtn.addEventListener('click', toggleTestMode);
    
    // 录音按钮
    recordBtn.addEventListener('click', toggleRecording);
    
    // 文本框编辑
    transcriptText.addEventListener('input', () => {
        currentTranscript = transcriptText.value;
    });
    
    // 重置时清除 STT 模型显示
    function resetSTTModelDisplay() {
        if (sttModelInfo) {
            sttModelInfo.textContent = 'STT: -';
            currentSTTModel = '';
        }
    }
    
    // 测试模式下的手动操作按钮
    analyzeBtn.addEventListener('click', () => {
        analyzeTranscriptManual(transcriptText.value);
    });
    
    confirmBtn.addEventListener('click', () => {
        addToCalendar();
    });
    
    undoBtn.addEventListener('click', () => {
        undoLastEvents();
    });
    
    // Electron IPC
    if (window.electronAPI) {
        window.electronAPI.onToggleRecording(() => {
            toggleRecording();
        });
        
        window.electronAPI.onCalendarAdded((data) => {
            if (data.success) {
                const count = data.count || 1;
                showStatus(`✅ 已添加 ${count} 个事件到苹果日历！`);
                setTimeout(() => {
                    resetUI();
                }, 2000);
            } else {
                showStatus(`❌ 添加失败: ${data.error}`);
            }
        });
    }
}

// 切换测试模式
function toggleTestMode() {
    testMode = !testMode;
    testModeBtn.textContent = testMode ? '自动' : '测试';
    testModeBtn.classList.toggle('active', testMode);
    saveTestMode();
    showStatus(testMode ? '🧪 测试模式：每步需手动确认' : '🚀 自动模式：自动完成所有步骤');
    setTimeout(() => hideStatus(), 2000);
}

// 保存/加载测试模式状态
function saveTestMode() {
    localStorage.setItem('testMode', testMode);
}

function loadTestMode() {
    testMode = localStorage.getItem('testMode') === 'true';
    testModeBtn.textContent = testMode ? '自动' : '测试';
    testModeBtn.classList.toggle('active', testMode);
}

// 切换录音状态
async function toggleRecording() {
    if (!isRecording) {
        await startRecording();
    } else {
        await stopRecording();
    }
}

// 开始录音
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
        recordBtn.classList.add('recording');
        recordText.textContent = '停止';
        showStatus('🎤 正在录音...');
        
        // 重置UI
        textArea.classList.add('hidden');
        timeDataArea.classList.add('hidden');
        manualActions.classList.add('hidden');
    } catch (error) {
        console.error('录音错误:', error);
        showStatus('❌ 无法访问麦克风');
    }
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordText.textContent = '开始';
        showStatus('⏳ 处理中...');
    }
}

// 处理音频（自动模式）
async function processAudio(audioBlob) {
    try {
        // 1. 转录
        showStatus('📝 正在转录...');
        const transcribeResult = await transcribeAudio(audioBlob);
        
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

        // 显示转写文本和模型信息
        currentTranscript = transcript;
        currentSTTModel = model;
        transcriptText.value = transcript;
        updateSTTModelDisplay(model);
        textArea.classList.remove('hidden');
        
        if (testMode) {
            // 测试模式：等待用户点击"识别时间点"
            showStatus('✅ 转录完成，请点击"识别时间点"按钮');
            // 确保按钮区域可见
            manualActions.classList.remove('hidden');
            analyzeBtn.classList.remove('hidden');
            confirmBtn.classList.add('hidden');
            // 显示时间数据区域（即使还没有数据，也要显示按钮）
            timeDataArea.classList.remove('hidden');
            return;
        }

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
        const analysis = await analyzeTranscriptAPI(transcript);
        
        if (!analysis || !analysis.success || !analysis.data) {
            showStatus('❌ 分析失败');
            return;
        }

        // 处理返回的数据（可能是数组或单个对象）
        const data = analysis.data;
        if (Array.isArray(data)) {
            currentEvents = data;
            currentEventData = data.length > 0 ? data[0] : null; // 兼容旧代码
            displayTimeDataMultiple(data);
        } else {
            currentEvents = [data];
            currentEventData = data;
            displayTimeData(data);
        }
        
        if (testMode) {
            // 测试模式：等待用户点击"确认写入日历"
            const count = currentEvents.length;
            showStatus(`✅ 分析完成，识别到 ${count} 个时间块，请点击"确认写入日历"按钮`);
            confirmBtn.classList.remove('hidden');
            undoBtn.classList.remove('hidden'); // 显示撤回按钮
            return;
        }

        // 自动模式：直接写入日历
        await addToCalendar();
        
    } catch (error) {
        console.error('分析错误:', error);
        showStatus('❌ 分析失败: ' + (error.message || error));
    }
}

// 等待日历添加完成的 Promise 包装器（单个事件，保留兼容性）
function addToCalendarPromise() {
    return addMultipleToCalendarPromise([currentEventData]);
}

// 分析文本（测试模式手动调用）
async function analyzeTranscriptManual(transcript) {
    try {
        showStatus('🤖 正在分析...');
        const analysis = await analyzeTranscriptAPI(transcript);
        
        if (!analysis || !analysis.success || !analysis.data) {
            showStatus('❌ 分析失败');
            return;
        }

        // 处理返回的数据（可能是数组或单个对象）
        const data = analysis.data;
        if (Array.isArray(data)) {
            currentEvents = data;
            currentEventData = data.length > 0 ? data[0] : null; // 兼容旧代码
            displayTimeDataMultiple(data);
        } else {
            currentEvents = [data];
            currentEventData = data;
            displayTimeData(data);
        }
        
        // 确保时间数据区域和按钮可见
        timeDataArea.classList.remove('hidden');
        manualActions.classList.remove('hidden');
        
        if (testMode) {
            const count = currentEvents.length;
            showStatus(`✅ 分析完成，识别到 ${count} 个时间块，请点击"确认写入日历"按钮`);
            confirmBtn.classList.remove('hidden');
            undoBtn.classList.remove('hidden'); // 显示撤回按钮
            analyzeBtn.classList.add('hidden'); // 隐藏"识别时间点"按钮
        }
        
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
function updateSTTModelDisplay(model) {
    console.log('updateSTTModelDisplay called:', { model, sttModelInfo: !!sttModelInfo });
    if (sttModelInfo && model) {
        // 格式化模型名称显示
        let displayName = model;
        if (model.includes('FunASR') || model.includes('funasr')) {
            displayName = 'FunASR';
        } else if (model.includes('Faster-Whisper') || model.includes('Whisper')) {
            displayName = model.replace('Faster-Whisper-', 'Whisper ').replace('Faster-', '');
        } else if (model === 'cloud' || model === '云端') {
            displayName = '云端 API';
        }
        sttModelInfo.textContent = `STT: ${displayName}`;
        sttModelInfo.title = `当前使用的语音转写模型: ${model}`;
        console.log('STT 模型显示已更新:', displayName);
    } else {
        console.warn('无法更新 STT 模型显示:', { sttModelInfo: !!sttModelInfo, model });
    }
}

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

// 显示时间数据（单个事件）
function displayTimeData(data) {
    dataActivity.textContent = data.activity || '-';
    dataStartTime.textContent = data.start_time ? formatDateTime(data.start_time) : '-';
    dataEndTime.textContent = data.end_time ? formatDateTime(data.end_time) : '-';
    dataDescription.textContent = data.description || data.status || '-';
    timeDataArea.classList.remove('hidden');
}

// 显示多个时间数据
function displayTimeDataMultiple(events) {
    if (events.length === 0) {
        displayTimeData({});
        return;
    }
    
    // 显示第一个事件的详细信息
    displayTimeData(events[0]);
    
    // 如果有多个事件，在描述中显示总数
    if (events.length > 1) {
        const originalDesc = dataDescription.textContent;
        dataDescription.textContent = `${originalDesc} (共 ${events.length} 个时间块)`;
    }
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
        
        if (window.electronAPI) {
            // Electron 模式：通过 IPC 批量添加
            await addMultipleToCalendarPromise(currentEvents);
            showStatus(`✅ 已添加 ${count} 个事件到苹果日历！`);
            setTimeout(() => {
                resetUI();
            }, 2000);
        } else {
            // 网页端：使用 API 批量添加
            await addMultipleToCalendarAPI(currentEvents);
            showStatus(`✅ 已添加 ${count} 个事件到日历！`);
            setTimeout(() => {
                resetUI();
            }, 2000);
        }
    } catch (error) {
        console.error('添加到日历错误:', error);
        showStatus('❌ 添加失败: ' + (error.message || error));
    }
}

// 通过 API 批量添加到日历
async function addMultipleToCalendarAPI(events) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/calendar/add-multiple`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(events),
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
        if (result.success) {
            const count = result.deleted_count || 1;
            showStatus(`✅ 已撤回 ${count} 个事件`);
            setTimeout(() => {
                resetUI();
            }, 2000);
        } else {
            throw new Error(result.error || '撤回失败');
        }
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
function resetUI() {
    textArea.classList.add('hidden');
    timeDataArea.classList.add('hidden');
    manualActions.classList.add('hidden');
    analyzeBtn.classList.remove('hidden');
    confirmBtn.classList.add('hidden');
    undoBtn.classList.add('hidden');
    currentTranscript = '';
    currentEventData = null;
    currentEvents = [];
    currentSTTModel = '';
    transcriptText.value = '';
    if (sttModelInfo) {
        sttModelInfo.textContent = 'STT: -';
    }
    hideStatus();
}
