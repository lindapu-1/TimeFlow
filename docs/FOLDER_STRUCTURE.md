# TimeFlow 文件夹结构说明

## 📁 当前文件夹结构分析

### 根目录文件

#### 核心代码文件
- `app.py` - FastAPI 后端主程序（核心）
- `prompts.md` - LLM Prompt 模板文件（可编辑）
- `requirements.txt` - Python 依赖包列表

#### 测试脚本（散落在根目录）
- `test_*.py` - 各种测试脚本
- `benchmark_*.py` - 基准测试脚本
- `quick_test_*.py` - 快速测试脚本

#### 文档文件（散落在根目录，共 30+ 个）
- `README.md` - 项目主说明文档
- `Brief.md` - 项目简介
- `QUICKSTART.md` - 快速开始指南
- `🌟COMPREHENSIVE_STT_BENCHMARK_REPORT.md` - STT 基准测试报告
- `STT_BENCHMARK_*.md` - STT 相关文档
- `OLLAMA_*.md` - Ollama 相关文档
- `CHINESE_STT_*.md` - 中文 STT 相关文档
- `CLOUD_STT_*.md` - 云端 STT 相关文档
- `FRONTEND_FRAMEWORK_RESEARCH.md` - 前端框架研究
- `APP_DISTRIBUTION_GUIDE.md` - 应用分发指南
- `MAC_APP_GUIDE.md` - Mac 应用指南
- `HOTKEY_RECORDING_TEST.md` - 快捷键录音测试
- `DAYFLOW_TECH_ANALYSIS.md` - 技术分析
- `IMPLEMENTATION_PLAN.md` - 实现计划
- 等等...

#### JSON 结果文件（散落在根目录）
- `*_results.json` - 各种基准测试结果
- `*_benchmark_results.json` - 基准测试结果

#### Shell 脚本
- `fix_permissions.sh` - 修复权限脚本
- `start_hotkey_test.sh` - 启动快捷键测试脚本

---

### 子文件夹说明

#### 1. `CalendarApp/` - Electron 前端应用（当前使用）
**作用**：TimeFlow 的 Electron 桌面应用前端

**包含**：
- `main.js` - Electron 主进程
- `preload.js` - Electron 预加载脚本
- `package.json` - Node.js 依赖配置
- `static/` - 前端静态文件
  - `index.html` - 前端页面
  - `script.js` - 前端逻辑
  - `style.css` - 样式文件
- `test_*.py` - 日历相关测试脚本
- `测试录音/` - 测试用的音频文件
- `brief.md` - CalendarApp 项目说明
- `README.md` - CalendarApp 说明文档

#### 2. `electron/` - 另一个 Electron 文件夹（可能是旧版本）
**作用**：可能是早期版本的 Electron 实现

**包含**：
- `main.js`, `preload.js` - Electron 文件
- `package.json` - Node.js 配置
- 各种文档（QUICKSTART.md, README.md 等）

**建议**：如果 `CalendarApp/` 是当前使用的版本，这个文件夹可以删除或归档

#### 3. `static/` - 静态文件（可能是旧版本前端）
**作用**：可能是早期版本的 Web 前端

**包含**：
- `index.html` - HTML 页面
- `script.js` - JavaScript 逻辑
- `style.css` - CSS 样式

**建议**：如果 `CalendarApp/static/` 是当前使用的版本，这个文件夹可以删除或归档

#### 4. `data/` - 数据文件
**作用**：存储应用运行时数据

**包含**：
- `time_log.json` - 时间记录日志
- `recent_event.json` - 最近写入的日历事件（用于撤回功能）

---

## 🗂️ 建议的文件夹整理方案

### 方案：创建分类文件夹

```
TimeFlow/
├── app.py                    # 核心代码
├── prompts.md                # Prompt 模板
├── requirements.txt          # Python 依赖
├── README.md                 # 主说明文档
│
├── docs/                     # 📚 所有文档（新建）
│   ├── guides/               # 指南文档
│   │   ├── QUICKSTART.md
│   │   ├── APP_DISTRIBUTION_GUIDE.md
│   │   ├── MAC_APP_GUIDE.md
│   │   └── ...
│   ├── research/             # 研究文档
│   │   ├── FRONTEND_FRAMEWORK_RESEARCH.md
│   │   ├── CHINESE_STT_RESEARCH.md
│   │   ├── OLLAMA_MODELS_RESEARCH.md
│   │   └── ...
│   ├── benchmarks/           # 基准测试报告
│   │   ├── STT_BENCHMARK_RESULTS.md
│   │   ├── OLLAMA_BENCHMARK_RESULTS.md
│   │   ├── 🌟COMPREHENSIVE_STT_BENCHMARK_REPORT.md
│   │   └── ...
│   ├── setup/                # 设置文档
│   │   ├── OLLAMA_SETUP.md
│   │   ├── LOCAL_STT_SETUP.md
│   │   ├── CLOUD_STT_SETUP.md
│   │   └── ...
│   └── tests/                # 测试文档
│       ├── HOTKEY_RECORDING_TEST.md
│       ├── FASTER_WHISPER_TEST_RESULTS.md
│       └── ...
│
├── tests/                    # 🧪 测试脚本（新建）
│   ├── test_ollama.py
│   ├── test_faster_whisper.py
│   ├── test_hotkey_recording.py
│   ├── test_elevenlabs_scribe.py
│   ├── quick_test_ollama.py
│   └── ...
│
├── benchmarks/               # 📊 基准测试脚本和结果（新建）
│   ├── scripts/              # 基准测试脚本
│   │   ├── benchmark_stt_models.py
│   │   ├── benchmark_ollama_models.py
│   │   ├── benchmark_chinese_stt.py
│   │   └── benchmark_cloud_stt.py
│   └── results/              # 基准测试结果 JSON
│       ├── stt_benchmark_results.json
│       ├── ollama_benchmark_results.json
│       ├── doubao_benchmark_results.json
│       └── ...
│
├── scripts/                  # 🔧 Shell 脚本（新建）
│   ├── fix_permissions.sh
│   └── start_hotkey_test.sh
│
├── CalendarApp/              # Electron 前端应用（保持不变）
│   ├── main.js
│   ├── preload.js
│   ├── static/
│   ├── test_*.py
│   └── ...
│
├── data/                     # 数据文件（保持不变）
│   ├── time_log.json
│   └── recent_event.json
│
└── archive/                   # 📦 归档文件夹（新建，可选）
    ├── electron/             # 旧版本 Electron
    └── static/                # 旧版本静态文件
```

---

## 📋 文档分类说明

### docs/guides/ - 使用指南
- 快速开始、安装指南、使用教程

### docs/research/ - 技术研究
- 技术选型研究、模型对比、框架分析

### docs/benchmarks/ - 基准测试报告
- 各种模型的性能测试报告

### docs/setup/ - 设置文档
- 各种工具和服务的安装配置指南

### docs/tests/ - 测试文档
- 测试结果、测试报告

---

## 🚀 整理步骤

1. **创建新文件夹**：`docs/`, `tests/`, `benchmarks/`, `scripts/`, `archive/`
2. **移动文档**：将所有 `.md` 文件按分类移动到 `docs/` 子文件夹
3. **移动测试脚本**：将所有 `test_*.py` 移动到 `tests/`
4. **移动基准测试**：将 `benchmark_*.py` 移动到 `benchmarks/scripts/`，JSON 结果移动到 `benchmarks/results/`
5. **移动脚本**：将 `.sh` 文件移动到 `scripts/`
6. **归档旧文件**：将 `electron/` 和 `static/` 移动到 `archive/`（如果不再使用）

---

## ✅ 整理后的优势

1. **清晰的结构**：文档、代码、测试分离
2. **易于查找**：按功能分类，快速定位
3. **易于维护**：新文档有明确的存放位置
4. **减少混乱**：根目录只保留核心文件

