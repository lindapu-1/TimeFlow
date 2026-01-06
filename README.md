# TimeFlow MVP

通过语音输入自动记录时间分配的应用。

## 功能特性

- 🎤 语音录制：点击按钮录制语音
- 📝 自动转录：将语音转换为文字
- 🤖 AI 分析：从语音文本中提取时间信息（开始时间、结束时间、活动名称）
- 📊 时间记录：自动保存到时间日志
- 📈 时间总结：生成每日时间分配总结

## 技术栈

- **前端**: HTML + JavaScript (Web Audio API)
- **后端**: FastAPI (Python)
- **语音转录**: AI Builder Audio Transcription API
- **AI 分析**: AI Builder Chat Completions API

## 快速开始

### 1. 安装依赖

```bash
cd TimeFlow
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```
SUPER_MIND_API_KEY=your_api_key_here
```

### 3. 启动服务

```bash
python app.py
```

### 4. 打开浏览器

访问 `http://127.0.0.1:8000`

## 使用示例

### 语音输入示例

- "我刚刚吃完饭了"
- "过去的 2 小时我在做家务"
- "我接下来打算开始看书"
- "从 9 点到 11 点我在开会"

系统会自动识别：
- 活动名称（如：吃饭、做家务、看书、开会）
- 时间范围（开始时间、结束时间）
- 当前状态（刚完成、正在进行、即将开始）

## 项目结构

```
TimeFlow/
├── app.py                 # FastAPI 后端应用
├── static/
│   ├── index.html         # 前端页面
│   ├── script.js          # 前端逻辑（语音录制、UI交互）
│   └── style.css          # 样式文件
├── data/
│   └── time_log.json       # 时间记录数据（JSON格式）
├── requirements.txt       # Python 依赖
├── .env                   # 环境变量（不提交到git）
└── README.md              # 本文件
```

## MVP 目标

根据 Brief.md 中的 OKRs：

- ✅ **Key Result 1**: 可以识别语音输入，快速且精准转成文字
- ✅ **Key Result 2**: 通过 AI 分析后，生成对应的时间记录数据结构

## 进阶计划

1. Mac 本地 App（快捷键输入）
2. 手机 App + Watch 联动
3. 自动检测截图记录时间
4. 时间分配分析和可视化




