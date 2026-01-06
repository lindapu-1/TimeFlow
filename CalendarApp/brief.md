我可以用本地模型+本地语音输入，实现在苹果原生日历上的时间记录功能，通过快捷键来记录时间，并且把时间记录渲染到日历上。此时仅需要一个很小的 app 页面，比如上面只有一个按钮，可以通过按钮来进行操作，也可以通过按快捷键。

objective:
- 支持通过语音输入来记录时间点的 APP：
- step 1：语音转文字，用 faster whisper 本地模型
- step 2: 文字转时间点，用 ollama 本地模型
  -  根据所需的时间点数据结构，提取出所需的字段：
    - **必需字段（3个）：**
      - `summary` (活动名称) - 从文本提取 activity
      - `start date` (开始时间) - 从文本提取 start_time
      - `end date` (结束时间) - 从文本提取 end_time
    - **可选字段（1个）：**
      - `description` (详细描述) - 扩展当前实现，可包含原始文本



- 后端测试：通过 api 测试后端模型是否可以正常工作：
- 1. 测试语音转文字模型：通过本地语音转文字模型测试语音转文字模型的转写时间，找到最快和最准的本地语音转文字模型：使用FunASR（默认 Funasr，fallback faster whisper small ）
- 2. 测试时间点提取模型的 prompt
- 3. 测试时间点提取模型的效率：lamma3.2（不准，无法正确推理）；确定Fallback逻辑：Doubao → Supermind → Ollama
- 4. 测试写入苹果日历：根据测试案例，测试写入苹果日历的请求（必须要用更智能的云端模型）
- 5. 测试苹果日历撤回功能：能否一键通过请求撤回刚刚模型写入的日历事件？比如刚刚一句话写入的事件可以撤回。
- 
- 前端页面
- 所有元素：1录音按钮，2文本框（默认为空），3时间数据结构（默认为空）
  - 元素 1：录音按钮
    - 显示”开始“，当点击之后开始通过系统 mic 录音，并将录音送入 faster whisper 模型快速识别成文字
  - 识别出文字后，显示在界面上，并且可以编辑
-  元素 2：文本框
   -  用户录音结束后，转写出的文字会显示在文本框中，并且可以直接编辑；
-  元素 3：根据转写文本，提取时间数据结构，并显示在界面上
-  workflow：用户录音结束后，自动转写成文本并记录进入日历，中间无需用户进行任何手动操作
   -  支持测试模式。如果点击右上角的测试按钮，则每一步都需要手动点击才进行下一步操作（录音结束生成文本后，点击按钮识别时间点，再点击确认后才写入苹果日历）
-  整个 app 框打开后可拖动




指南：
后端支持的操作：

## 📋 完整的 API 列表

| 方法 | 路径 | 功能 | 说明 | 状态 |
|------|------|------|------|------|
| GET | `/` | 返回前端页面 | 静态文件服务，优先使用 CalendarApp/static | ✅ 完成 |
| POST | `/chat` | Chat 对话 | 通用 LLM 对话接口（Supermind） | ✅ 完成 |
| POST | `/api/transcribe` | 转录音频 | FunASR → Faster Whisper → 云端 API | ✅ 完成 |
| POST | `/api/analyze` | 提取时间事件 | Doubao → Supermind → Ollama | ✅ 完成 |
| POST | `/api/calendar/add` | 添加单个事件 | 写入 Apple Calendar（通过 AppleScript） | ✅ 完成 |
| POST | `/api/calendar/add-multiple` | 批量添加事件 | 写入多个事件，支持一次操作添加多个 | ✅ 完成 |
| POST | `/api/calendar/undo` | 撤回事件 | 撤回最近一次操作的所有事件（可能多个） | ✅ 完成 |
| POST | `/api/time-entry` | 保存时间记录 | 保存到本地 JSON 文件（`data/time_log.json`） | ✅ 完成 |
| GET | `/api/time-entries` | 查询时间记录 | 支持按日期过滤（`?date=YYYY-MM-DD`） | ✅ 完成 |

## 🔧 后端实现细节

### 1. 语音转文字（STT）

**优先级机制**：
1. **FunASR**（默认，中文识别最准确）
   - 模型：`paraformer-zh-16k-v2`
   - 懒加载机制，首次调用时加载
   - 环境变量：`USE_FUNASR=true`（默认）
   - 环境变量：`FUNASR_MODEL=paraformer-zh-16k-v2`

2. **Faster Whisper**（备用）
   - 模型大小：`tiny`（最快，0.3秒）
   - 支持：`tiny`, `base`, `small`, `medium`, `large`
   - 环境变量：`USE_LOCAL_STT=true`
   - 环境变量：`WHISPER_MODEL_SIZE=tiny`

3. **云端 API**（最后备用）
   - Supermind API：`https://space.ai-builders.com/backend/v1/audio/transcriptions`

**API 参数**：
- `audio_file`: 音频文件（multipart/form-data）
- `language`: 语言代码（默认 `zh-CN`）
- `use_local`: 是否强制使用本地模型（可选）

**返回格式**：
```json
{
  "success": true,
  "transcript": "转写文本",
  "method": "funasr|whisper|cloud",
  "duration": 0.5
}
```

### 2. 时间事件提取（LLM）

**优先级机制**：
1. **Doubao**（默认，最快最准确）
   - 模型：`doubao-1-5-lite-32k-250115`
   - API URL：`https://ark.cn-beijing.volces.com/api/v3`
   - 性能：2.79秒，95.2% 准确率
   - 环境变量：`USE_DOUBAO=true`（默认）
   - 环境变量：`DOUBAO_API_KEY=...`
   - 环境变量：`DOUBAO_MODEL=doubao-1-5-lite-32k-250115`

2. **Supermind**（第二优先级）
   - 模型：`supermind-agent-v1`
   - API URL：`https://space.ai-builders.com/backend/v1`
   - 环境变量：`USE_SUPERMIND=true`（默认）
   - 环境变量：`SUPER_MIND_API_KEY` 或 `AI_BUILDER_TOKEN`

3. **Ollama**（本地备用）
   - 模型：`llama3.2:latest`（最快本地模型，3秒）
   - API URL：`http://localhost:11434`
   - 环境变量：`USE_OLLAMA=false`（默认）
   - 环境变量：`OLLAMA_MODEL=llama3.2:latest`

**Prompt 优化**：
- ✅ 支持多时间块提取（必须全部提取，不遗漏）
- ✅ 支持相对时间推理（"刚刚"、"刚才"、"半小时前"）
- ✅ 24小时制时间格式
- ✅ 强调相对时间是过去的时间（结束时间=当前时间）
- ✅ 包含当前时间信息，动态计算相对时间

**后处理逻辑**：
- ✅ **模型名称标记**：自动在每个时间块的 `description` 字段末尾添加 `[模型: {model_name}]`
- ✅ **相对时间修正**：检测相对时间关键词，如果结束时间与当前时间相差超过5分钟，自动修正为当前时间
- ✅ **多时间块支持**：返回数组格式，即使只有一个时间块也返回数组

**API 参数**：
- `transcript`: 转录文本（必需）
- `use_ollama`: 是否强制使用 Ollama（可选，默认 false）

**返回格式**：
```json
{
  "success": true,
  "data": [
    {
      "activity": "活动名称",
      "start_time": "2026-01-06T08:00:00",
      "end_time": "2026-01-06T09:00:00",
      "location": "地点或null",
      "description": "描述 [模型: doubao-1-5-lite-32k-250115]"
    }
  ],
  "raw_response": "AI原始响应",
  "method": "doubao|supermind|ollama",
  "model": "模型名称"
}
```

### 3. Apple Calendar 集成

**实现方式**：
- ✅ 通过 `subprocess` 调用 `osascript` 执行 AppleScript
- ✅ 写入到 "TimeFlow" 日历（自动创建）
- ✅ 返回事件 ID（用于撤回）
- ✅ 支持批量添加多个事件

**AppleScript 功能**：
- ✅ 创建日历事件（标题、开始时间、结束时间、描述、地点）
- ✅ 通过事件 ID 删除事件
- ✅ 转义特殊字符（防止 AppleScript 注入）

**事件存储**：
- ✅ 最近一次操作的所有事件信息保存在 `data/recent_event.json`
- ✅ 包含：`event_ids`（数组）、`events`（完整数据）、`created_at`、`count`

**API 端点**：
- `/api/calendar/add`: 单个事件
- `/api/calendar/add-multiple`: 多个事件（批量）
- `/api/calendar/undo`: 撤回最近一次操作的所有事件

### 4. 时间记录存储

**文件存储**：
- ✅ `data/time_log.json`: 所有时间记录条目
- ✅ `data/recent_event.json`: 最近写入的日历事件（用于撤回）

**数据模型**：
```python
class TimeEntry(BaseModel):
    activity: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_minutes: Optional[int]
    status: Optional[str] = "completed"
    description: Optional[str]
    location: Optional[str]
```

**API 功能**：
- ✅ 保存时间记录：`POST /api/time-entry`
- ✅ 查询时间记录：`GET /api/time-entries?date=YYYY-MM-DD`

### 5. 数据模型（Pydantic）

**请求模型**：
- `ChatRequest`: Chat 对话请求
- `TimeAnalysisRequest`: 时间分析请求（`transcript`, `use_ollama`）
- `CalendarEventRequest`: 日历事件请求（`activity`, `start_time`, `end_time`, `description`, `location`）
- `TimeEntry`: 时间记录条目

**响应格式**：
- 统一使用 `{"success": true/false, ...}` 格式
- 错误时返回 `{"success": false, "error": "错误信息"}`

### 6. 错误处理和日志

**日志系统**：
- ✅ 使用 Python `logging` 模块
- ✅ 日志级别：INFO
- ✅ 记录关键操作：模型调用、API 请求、错误信息

**错误处理**：
- ✅ JSON 解析错误：自动尝试修复（提取 markdown 代码块中的 JSON）
- ✅ API 调用失败：自动 fallback 到下一个优先级
- ✅ AppleScript 执行失败：返回详细错误信息
- ✅ 超时处理：60秒超时限制

### 7. CORS 配置

- ✅ 允许所有来源（开发环境）
- ✅ 支持所有 HTTP 方法
- ✅ 支持所有请求头

## 📊 测试状态

### ✅ 已完成测试

1. **STT 模型基准测试**
   - ✅ FunASR vs Faster Whisper vs 云端 API
   - ✅ 速度、准确性对比
   - ✅ 文档：`🌟COMPREHENSIVE_STT_BENCHMARK_REPORT.md`

2. **LLM 模型基准测试**
   - ✅ Ollama 模型对比（llama3.2, qwen, deepseek-r1）
   - ✅ 云端模型对比（Doubao, Supermind）
   - ✅ 文档：`OLLAMA_BENCHMARK_RESULTS.md`, `CLOUD_VS_LOCAL_LLM_COMPARISON.md`

3. **日历写入测试**
   - ✅ 单个事件写入
   - ✅ 多个事件批量写入
   - ✅ 相对时间处理
   - ✅ 测试脚本：`test_calendar_write.py`

4. **撤回功能测试**
   - ✅ 单个事件撤回
   - ✅ 多个事件批量撤回
   - ✅ 测试脚本：`test_calendar_undo.py`

### 🔄 待测试/优化

- [ ] 生产环境 CORS 配置（限制来源）
- [ ] 错误重试机制
- [ ] 性能监控和指标收集
- [ ] API 限流和防刷机制

## 📚 API 文档访问

启动后端服务后，访问以下地址查看完整 API 文档：

- **Swagger UI**（推荐）：`http://127.0.0.1:8000/docs`
- **ReDoc**：`http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**：`http://127.0.0.1:8000/openapi.json`

## 🚀 启动后端服务

```bash
cd TimeFlow
python3 app.py
```

服务默认运行在：`http://127.0.0.1:8000`


