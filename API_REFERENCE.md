# TimeFlow API 调用参考

本文档列出了 TimeFlow 项目中所有调用的 API，包括它们的优先级、用途和配置方式。

---

## 📋 API 分类

项目中的 API 调用分为三大类：
1. **STT（语音转文字）API**
2. **LLM（大语言模型）API** - 用于时间事件提取
3. **Chat API** - 通用对话接口

---

## 1. STT（语音转文字）API

### 优先级顺序

| 优先级 | API/模型 | 类型 | 默认状态 |
|--------|---------|------|---------|
| **1️⃣** | **云端 STT API** | 云端 | ✅ **默认启用** |
| **2️⃣** | **Faster Whisper** | 本地 | ⚠️ 备用 |

### 1.1 云端 STT API（第一优先级）⭐

**API 端点**：
```
POST https://space.ai-builders.com/backend/v1/audio/transcriptions
```

**认证**：
- Header: `Authorization: Bearer {AI_BUILDER_TOKEN}` 或 `Authorization: Bearer {SUPER_MIND_API_KEY}`

**请求参数**：
- `audio_file`: 音频文件（multipart/form-data）
- `language`: 语言代码（默认 `zh-CN`）

**特点**：
- ✅ **准确率最高**：95%+（根据测试对比）
- ✅ **响应时间**：1-2 秒
- ✅ **内存占用**：< 100 MB（适合云端部署）
- ✅ **自动使用**：无需额外配置

**环境变量**：
```bash
# 至少配置一个
AI_BUILDER_TOKEN=your_token
# 或
SUPER_MIND_API_KEY=your_key
```

**代码位置**：
- `app.py` 第 183 行：`TRANSCRIPTION_API_URL`
- `app.py` 第 974-1017 行：云端 API 调用逻辑

---

### 1.2 Faster Whisper（第二优先级）⭐

**类型**：本地模型（需要安装）

**模型配置**：
- 默认模型：`tiny`（最快，0.4秒）
- 可选模型：`tiny`, `base`, `small`, `medium`, `large`

**特点**：
- ⚡ **速度快**：0.4 秒（比云端快）
- ⚠️ **准确率较低**：约 62% 相似度（相比云端 API）
- ⚠️ **内存占用**：200-300 MB（可能超出 256MB 限制）
- 📝 **输出问题**：繁体字、标点不规范

**环境变量**：
```bash
USE_LOCAL_STT=true  # 启用本地模型
WHISPER_MODEL_SIZE=tiny  # 模型大小
```

**代码位置**：
- `app.py` 第 195-196 行：配置
- `app.py` 第 1019-1053 行：Faster Whisper 调用逻辑

**使用场景**：
- 网络不可用时
- 需要离线处理时
- 云端 API 失败时的回退

---

## 2. LLM（大语言模型）API - 时间事件提取

### 优先级顺序

| 优先级 | API/模型 | 类型 | 默认状态 |
|--------|---------|------|---------|
| **1️⃣** | **Doubao API** | 云端 | ✅ **默认启用** |
| **2️⃣** | **Supermind API** | 云端 | ✅ 自动回退 |
| **3️⃣** | **Ollama API** | 本地 | ⚠️ 可选 |

### 2.1 Doubao API（第一优先级）⭐⭐⭐⭐⭐

**API 端点**：
```
POST https://ark.cn-beijing.volces.com/api/v3/chat/completions
```

**认证**：
- Header: `Authorization: Bearer {DOUBAO_API_KEY}`

**模型**：
- 默认：`doubao-1-5-lite-32k-250115`
- 性能：2.79秒，95.2% 准确率（根据基准测试）

**特点**：
- ✅ **最快最准确**：2.79秒，95.2% 准确率
- ✅ **多时间块提取**：支持一次提取多个时间事件
- ✅ **相对时间推理**：支持"刚刚"、"刚才"等相对时间

**环境变量**：
```bash
USE_DOUBAO=true  # 默认启用
DOUBAO_API_KEY=your_doubao_api_key  # 必需
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=doubao-1-5-lite-32k-250115
```

**代码位置**：
- `app.py` 第 205-212 行：配置
- `app.py` 第 1127-1150 行：Doubao API 调用逻辑

**请求示例**：
```python
response = requests.post(
    f"{DOUBAO_API_URL}/chat/completions",
    headers={
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1
    }
)
```

---

### 2.2 Supermind API（第二优先级）⭐⭐⭐

**API 端点**：
```
POST https://space.ai-builders.com/backend/v1/chat/completions
```

**认证**：
- Header: `Authorization: Bearer {AI_BUILDER_TOKEN}` 或 `Authorization: Bearer {SUPER_MIND_API_KEY}`

**模型**：
- `supermind-agent-v1`（多工具代理，支持 web search 和 Gemini handoff）

**特点**：
- ✅ **多工具支持**：自动 web search、URL 读取
- ✅ **自动回退**：Doubao 失败时自动使用
- ✅ **无需额外配置**：使用 AI_BUILDER_TOKEN

**环境变量**：
```bash
# 使用 AI_BUILDER_TOKEN（自动注入）或
SUPER_MIND_API_KEY=your_key
```

**代码位置**：
- `app.py` 第 176-180 行：OpenAI 客户端初始化
- `app.py` 第 1168-1189 行：Supermind API 调用逻辑

**请求示例**：
```python
response = client.chat.completions.create(
    model="supermind-agent-v1",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.3,
    max_tokens=500
)
```

---

### 2.3 Ollama API（第三优先级）⭐⭐

**API 端点**：
```
POST http://localhost:11434/api/generate
```

**认证**：
- 无需认证（本地服务）

**模型**：
- 默认：`llama3.2:latest`
- 性能：3秒（最快本地模型）

**特点**：
- ✅ **完全本地**：无需网络，数据隐私
- ⚠️ **需要安装**：需要本地运行 Ollama 服务
- ⚠️ **速度较慢**：3秒（比云端慢）

**环境变量**：
```bash
USE_OLLAMA=true  # 启用（默认 false）
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
```

**代码位置**：
- `app.py` 第 199-202 行：配置
- `app.py` 第 1190-1223 行：Ollama API 调用逻辑

**使用场景**：
- 需要完全离线处理
- 数据隐私要求高
- 云端 API 都不可用时

---

## 3. Chat API（通用对话接口）

### 3.1 Supermind Chat API

**API 端点**：
```
POST https://space.ai-builders.com/backend/v1/chat/completions
```

**认证**：
- Header: `Authorization: Bearer {AI_BUILDER_TOKEN}` 或 `Authorization: Bearer {SUPER_MIND_API_KEY}`

**支持的模型**：
- `deepseek` - 快速且经济
- `supermind-agent-v1` - 多工具代理
- `gemini-2.5-pro` - Google Gemini
- `gemini-3-flash-preview` - 快速 Gemini
- `gpt-5` - OpenAI 兼容
- `grok-4-fast` - X.AI Grok

**代码位置**：
- `app.py` 第 934-949 行：`/chat` 端点

**用途**：
- 通用对话功能
- 前端聊天界面

---

## 📊 API 优先级流程图

```
语音转文字 (STT)
├─ 1️⃣ 云端 STT API (默认)
│  └─ 失败 → 2️⃣ Faster Whisper
│     └─ 失败 → 返回错误
│
时间事件提取 (LLM)
├─ 1️⃣ Doubao API (默认)
│  └─ 失败 → 2️⃣ Supermind API
│     └─ 失败 → 3️⃣ Ollama API
│        └─ 失败 → 返回错误
```

---

## 🔐 API Keys 配置

### 必需配置

| API | 环境变量 | 说明 |
|-----|---------|------|
| **云端 STT** | `AI_BUILDER_TOKEN` 或 `SUPER_MIND_API_KEY` | 至少配置一个 |
| **Doubao** | `DOUBAO_API_KEY` | 可选（如果不配置，使用 Supermind） |

### 可选配置

| API | 环境变量 | 默认值 |
|-----|---------|--------|
| Doubao URL | `DOUBAO_API_URL` | `https://ark.cn-beijing.volces.com/api/v3` |
| Doubao Model | `DOUBAO_MODEL` | `doubao-1-5-lite-32k-250115` |
| Ollama URL | `OLLAMA_API_URL` | `http://localhost:11434` |
| Ollama Model | `OLLAMA_MODEL` | `llama3.2:latest` |
| Local STT | `USE_LOCAL_STT` | `false` |
| Whisper Size | `WHISPER_MODEL_SIZE` | `tiny` |

---

## 🚀 部署配置建议

### 云端部署（AI Builder Space）

**推荐配置**（最小内存占用）：
```json
{
  "env_vars": {
    "USE_LOCAL_STT": "false",
    "USE_DOUBAO": "true",
    "DOUBAO_API_KEY": "your_key",
    "AI_BUILDER_TOKEN": "auto_injected"
  }
}
```

**结果**：
- ✅ STT: 使用云端 API（准确率最高）
- ✅ LLM: 使用 Doubao（最快最准确）
- ✅ 内存占用: < 100 MB

### 本地开发

**推荐配置**：
```bash
# .env 文件
AI_BUILDER_TOKEN=your_token
DOUBAO_API_KEY=your_key
USE_LOCAL_STT=false  # 使用云端 API
USE_DOUBAO=true      # 使用 Doubao
```

---

## 📈 性能对比

### STT API 对比

| API | 响应时间 | 准确率 | 内存占用 | 推荐度 |
|-----|---------|--------|---------|--------|
| **云端 STT API** | 1-2秒 | **95%+** | < 100 MB | ⭐⭐⭐⭐⭐ |
| Faster Whisper | 0.4秒 | 62% | 200-300 MB | ⭐⭐ |

### LLM API 对比

| API | 响应时间 | 准确率 | 多时间块 | 推荐度 |
|-----|---------|--------|---------|--------|
| **Doubao** | **2.79秒** | **95.2%** | ✅ | ⭐⭐⭐⭐⭐ |
| Supermind | ~3-5秒 | ~90% | ✅ | ⭐⭐⭐ |
| Ollama | 3秒 | ~85% | ✅ | ⭐⭐ |

---

## 🔄 自动降级机制

代码实现了完整的自动降级机制：

1. **STT 降级**：
   - 云端 API → Faster Whisper → 错误

2. **LLM 降级**：
   - Doubao → Supermind → Ollama → 错误

3. **错误处理**：
   - 每个 API 调用都有异常处理
   - 失败时自动尝试下一个优先级
   - 所有方法都失败时返回明确的错误信息

---

## 📝 代码位置参考

| 功能 | 文件 | 行号 |
|------|------|------|
| STT 云端 API | `app.py` | 974-1017 |
| STT Faster Whisper | `app.py` | 1019-1053 |
| LLM Doubao | `app.py` | 1127-1150 |
| LLM Supermind | `app.py` | 1168-1189 |
| LLM Ollama | `app.py` | 1190-1223 |
| Chat API | `app.py` | 934-949 |
| API 配置 | `app.py` | 176-212 |

---

## ⚠️ 安全注意事项

1. **不要硬编码 API keys**：所有 keys 必须从环境变量读取
2. **不要提交 .env 文件**：确保在 `.gitignore` 中
3. **使用 .env.example**：作为配置模板
4. **部署时通过环境变量传递**：不要提交到代码仓库

详见 `SECURITY_GUIDE.md`
