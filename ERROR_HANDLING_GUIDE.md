# 错误处理指南

## 📋 概述

当 API 调用失败时（如达到使用限制），系统会返回详细的错误信息，包括：
- **失败步骤**：语音转文本 vs 时间提取
- **尝试的模型**：哪些模型被尝试了
- **错误详情**：每个模型的具体错误原因

---

## 🔍 错误响应格式

### 成功响应

```json
{
  "success": true,
  "transcript": "转写文本",
  "events": [...],
  "stt_method": "cloud",
  "llm_method": "doubao",
  "llm_model": "doubao-seed-1-6-251015"
}
```

### 失败响应（语音转文本步骤）

```json
{
  "success": false,
  "step": "语音转文本",
  "error": "所有转录方法都失败",
  "error_summary": "语音转文本步骤失败：已尝试 2 个模型，全部失败。详情：模型：云端 STT API - 已达到使用限制（429错误）；模型：Faster Whisper (tiny) - 模型未加载",
  "tried_models": [
    "云端 STT API",
    "Faster Whisper (tiny)"
  ],
  "errors": [
    "模型：云端 STT API - 已达到使用限制（429错误）",
    "模型：Faster Whisper (tiny) - 模型未加载"
  ]
}
```

### 失败响应（时间提取步骤）

```json
{
  "success": false,
  "step": "时间提取",
  "error": "时间提取步骤失败：已尝试 3 个模型，全部失败。详情：模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）；模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）；模型：Ollama (llama3.2:latest) - 服务器未运行",
  "error_summary": "时间提取步骤失败：已尝试 3 个模型，全部失败。详情：模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）；模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）；模型：Ollama (llama3.2:latest) - 服务器未运行",
  "tried_models": [
    "豆包 (doubao-seed-1-6-251015)",
    "Supermind (supermind-agent-v1)",
    "Ollama (llama3.2:latest)"
  ],
  "errors": [
    "模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）",
    "模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）",
    "模型：Ollama (llama3.2:latest) - 服务器未运行"
  ],
  "transcript": "转写文本"  // 即使分析失败，也返回转录文本
}
```

---

## 📱 iOS 快捷指令配置

### 错误处理步骤

在快捷指令中添加错误处理：

1. **检查响应**
   ```
   操作：从输入中获取词典值
   键: success
   ```

2. **如果失败**
   ```
   操作：如果
   条件: [success] 等于 false
   ```

3. **获取错误信息**
   ```
   操作：从输入中获取词典值
   键: step
   ```
   
   ```
   操作：从输入中获取词典值
   键: error_summary
   ```
   
   ```
   操作：从输入中获取词典值
   键: tried_models
   ```

4. **显示错误通知**
   ```
   操作：显示通知
   标题: [step] 失败
   内容: [error_summary]
   ```

### 完整错误处理流程

```
1. 获取 URL 内容
   URL: http://127.0.0.1:8000/api/mobile/process
   ...

2. 从输入中获取词典值
   键: success

3. 如果
   条件: [success] 等于 false
   然后：
     a. 从输入中获取词典值
        键: step
     b. 从输入中获取词典值
        键: error_summary
     c. 从输入中获取词典值
        键: tried_models
     d. 显示通知
        标题: ⚠️ [step] 失败
        内容: [error_summary]
        副标题: 已尝试模型：[tried_models]
   否则：
     a. 从输入中获取词典值
        键: events
     b. 为每个项目重复...
```

---

## 🔍 错误类型识别

### 429 错误（使用限制）

```json
{
  "errors": [
    "模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）"
  ]
}
```

**含义**：该模型的免费额度已用完

**解决方案**：
- 等待额度重置
- 切换到其他模型
- 升级到付费版本

### 401 错误（认证失败）

```json
{
  "errors": [
    "模型：云端 STT API - 认证失败（401错误）"
  ]
}
```

**含义**：API key 无效或过期

**解决方案**：
- 检查 API key 是否正确
- 更新 API key

### 连接失败

```json
{
  "errors": [
    "模型：Ollama (llama3.2:latest) - 服务器未运行"
  ]
}
```

**含义**：本地服务未启动

**解决方案**：
- 启动本地服务（如 Ollama）

---

## 📊 错误信息字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否成功 |
| `step` | string | 失败步骤："语音转文本" 或 "时间提取" |
| `error` | string | 错误消息 |
| `error_summary` | string | 错误摘要（包含所有尝试的模型和错误） |
| `tried_models` | array | 尝试的模型列表 |
| `errors` | array | 每个模型的详细错误信息 |

---

## 🎯 使用示例

### 示例 1：语音转文本失败

**响应**：
```json
{
  "success": false,
  "step": "语音转文本",
  "error_summary": "语音转文本步骤失败：已尝试 1 个模型，全部失败。详情：模型：云端 STT API - 已达到使用限制（429错误）",
  "tried_models": ["云端 STT API"],
  "errors": ["模型：云端 STT API - 已达到使用限制（429错误）"]
}
```

**快捷指令显示**：
```
⚠️ 语音转文本 失败

语音转文本步骤失败：已尝试 1 个模型，全部失败。详情：模型：云端 STT API - 已达到使用限制（429错误）

已尝试模型：云端 STT API
```

### 示例 2：时间提取失败

**响应**：
```json
{
  "success": false,
  "step": "时间提取",
  "error_summary": "时间提取步骤失败：已尝试 2 个模型，全部失败。详情：模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）；模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）",
  "tried_models": [
    "豆包 (doubao-seed-1-6-251015)",
    "Supermind (supermind-agent-v1)"
  ],
  "errors": [
    "模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）",
    "模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）"
  ],
  "transcript": "待会儿六点到六点半我要和学长一块吃晚饭"
}
```

**快捷指令显示**：
```
⚠️ 时间提取 失败

时间提取步骤失败：已尝试 2 个模型，全部失败。详情：模型：豆包 (doubao-seed-1-6-251015) - 已达到使用限制（429错误）；模型：Supermind (supermind-agent-v1) - 已达到使用限制（429错误）

已尝试模型：豆包 (doubao-seed-1-6-251015)、Supermind (supermind-agent-v1)

转写文本：待会儿六点到六点半我要和学长一块吃晚饭
```

---

## ✅ 检查清单

- [ ] 快捷指令中已添加错误检查
- [ ] 能够显示失败步骤（语音转文本 vs 时间提取）
- [ ] 能够显示尝试的模型列表
- [ ] 能够显示错误摘要
- [ ] 能够识别 429 错误（使用限制）
- [ ] 能够识别 401 错误（认证失败）

---

## 📚 相关文档

- [手机 API 参考](./MOBILE_API_REFERENCE.md) - API 详细说明
- [API 参考](./API_REFERENCE.md) - 完整 API 列表
