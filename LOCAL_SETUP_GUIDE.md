# 本地后端环境设置指南

## 🎯 目标

设置本地后端服务，以便在手机快捷指令上测试。

---

## ✅ 环境检查

### 1. Python 环境

```bash
python3 --version
# 应该显示 Python 3.9+ 
```

### 2. 项目目录

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
pwd
```

### 3. 依赖检查

```bash
python3 -c "import fastapi, uvicorn, openai, requests, httpx; print('✅ 核心依赖已安装')"
```

---

## 🔧 配置步骤

### 步骤 1：配置环境变量

检查 `.env` 文件是否存在：

```bash
ls -la .env
```

如果不存在，创建 `.env` 文件：

```bash
cp .env.example .env  # 如果 .env.example 存在
# 或手动创建
```

编辑 `.env` 文件，至少配置：

```bash
# 必需配置（至少配置一个）
AI_BUILDER_TOKEN=your_ai_builder_token_here
# 或
SUPER_MIND_API_KEY=your_supermind_api_key_here

# 可选配置
DOUBAO_API_KEY=your_doubao_api_key_here
USE_LOCAL_STT=false
USE_DOUBAO=true
```

**获取 API Token**：
- `AI_BUILDER_TOKEN`：通过 MCP 工具 `get_auth_token` 获取
- `DOUBAO_API_KEY`：从豆包平台获取

### 步骤 2：安装依赖（如果需要）

```bash
pip3 install -r requirements.txt
```

**注意**：如果只使用云端 API，不需要安装 `faster-whisper`（可选依赖）。

### 步骤 3：启动服务

**方式 A：使用启动脚本（推荐）**

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
./scripts/start_local_backend.sh
```

**方式 B：直接运行**

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
python3 app.py
```

**方式 C：使用 uvicorn（支持热重载）**

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### 步骤 4：验证服务

服务启动后，你应该看到：

```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**测试服务**：

```bash
# 测试根路径
curl http://127.0.0.1:8000/

# 测试 API 文档
open http://127.0.0.1:8000/docs
```

---

## 📱 手机快捷指令配置

### 问题：手机无法直接访问本地服务

**解决方案**：使用 **ngrok** 或 **Cloudflare Tunnel** 创建公网隧道

### 方式 A：使用 ngrok（推荐，最简单）

#### 1. 安装 ngrok

```bash
# macOS
brew install ngrok/ngrok/ngrok

# 或下载：https://ngrok.com/download
```

#### 2. 注册并获取 token

1. 访问：https://dashboard.ngrok.com/signup
2. 注册账号（免费）
3. 获取 authtoken
4. 配置：

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. 启动隧道

```bash
# 在另一个终端窗口
ngrok http 8000
```

你会看到：

```
Forwarding  https://xxxx-xxxx-xxxx.ngrok-free.app -> http://localhost:8000
```

**复制这个 URL**（例如：`https://xxxx-xxxx-xxxx.ngrok-free.app`）

#### 4. 配置手机快捷指令

在 iOS 快捷指令中：

1. **录制音频**
   - 操作：录制音频

2. **发送到云端**
   - 操作：获取 URL 内容
   - URL: `https://xxxx-xxxx-xxxx.ngrok-free.app/api/mobile/process`
   - 方法: POST
   - 请求体: 文件
   - 文件: [录制的音频]

3. **解析响应**
   - 操作：从输入中获取词典值
   - 键: `events`

4. **遍历事件**
   - 操作：为每个项目重复
   - 输入: [events 数组]

5. **添加日历事件**
   - 操作：添加日历事件
   - 标题: [activity]
   - 开始时间: [start_time]
   - 结束时间: [end_time]
   - 位置: [location]（如果有）
   - 备注: [description]（如果有）

---

### 方式 B：使用 Cloudflare Tunnel（免费，更稳定）

#### 1. 安装 cloudflared

```bash
# macOS
brew install cloudflared
```

#### 2. 启动隧道

```bash
cloudflared tunnel --url http://localhost:8000
```

你会看到：

```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable): |
|  https://xxxx-xxxx.trycloudflare.com                                                      |
+--------------------------------------------------------------------------------------------+
```

**复制这个 URL**

#### 3. 配置手机快捷指令

同上，使用 Cloudflare 的 URL。

---

## 🧪 测试流程

### 1. 本地测试（使用 curl）

```bash
# 测试移动端接口
curl -X POST http://127.0.0.1:8000/api/mobile/process \
  -F "audio_file=@test.m4a"

# 或使用 Swagger UI
open http://127.0.0.1:8000/docs
```

### 2. 通过隧道测试

```bash
# 使用 ngrok URL
curl -X POST https://xxxx-xxxx-xxxx.ngrok-free.app/api/mobile/process \
  -F "audio_file=@test.m4a"
```

### 3. 手机快捷指令测试

1. 打开快捷指令
2. 运行你创建的快捷指令
3. 录制音频
4. 查看结果

---

## 📋 完整示例：iOS 快捷指令配置

### 快捷指令名称

`TimeFlow - 语音记录时间`

### 操作步骤

1. **录制音频**
   ```
   操作：录制音频
   名称：录音
   ```

2. **发送到后端**
   ```
   操作：获取 URL 内容
   URL: https://your-ngrok-url.ngrok-free.app/api/mobile/process
   方法: POST
   请求体: 文件
   文件: [录音]
   ```

3. **检查响应**
   ```
   操作：如果
   条件: [URL 内容] 包含 "success"
   ```

4. **解析 JSON**
   ```
   操作：从输入中获取词典值
   键: events
   ```

5. **遍历事件**
   ```
   操作：为每个项目重复
   输入: [events]
   ```

6. **添加日历事件**
   ```
   操作：添加日历事件
   标题: [activity]
   开始时间: [start_time]
   结束时间: [end_time]
   位置: [location]
   备注: [description]
   ```

7. **显示结果**
   ```
   操作：显示通知
   标题: 成功
   内容: 已添加 [events 数量] 个事件到日历
   ```

---

## ⚠️ 常见问题

### Q1: 端口 8000 已被占用？

```bash
# 查找占用端口的进程
lsof -ti:8000

# 停止进程
kill $(lsof -ti:8000)

# 或使用其他端口
uvicorn app:app --host 127.0.0.1 --port 8001
```

### Q2: API key 未设置？

检查 `.env` 文件：

```bash
cat .env
```

确保至少配置了 `AI_BUILDER_TOKEN` 或 `SUPER_MIND_API_KEY`。

### Q3: ngrok 连接失败？

- 检查 ngrok 是否正在运行
- 检查本地服务是否在运行（`curl http://127.0.0.1:8000/`）
- 检查防火墙设置

### Q4: 手机无法访问 ngrok URL？

- 免费版 ngrok 需要访问验证页面（点击"Visit Site"）
- 或升级到付费版
- 或使用 Cloudflare Tunnel（无需验证）

---

## 🎯 快速启动命令

### 一键启动（推荐）

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
./scripts/start_local_backend.sh
```

### 启动 ngrok（另一个终端）

```bash
ngrok http 8000
```

### 测试

```bash
# 本地测试
curl http://127.0.0.1:8000/

# 通过 ngrok 测试
curl https://your-ngrok-url.ngrok-free.app/
```

---

## 📚 相关文档

- [手机 API 参考](./MOBILE_API_REFERENCE.md) - API 详细说明
- [API 参考](./API_REFERENCE.md) - 完整 API 列表
- [开发工作流程](./DEVELOPMENT_WORKFLOW.md) - 开发最佳实践

---

## ✅ 检查清单

- [ ] Python 3.9+ 已安装
- [ ] 项目目录正确
- [ ] `.env` 文件已配置（至少 `AI_BUILDER_TOKEN`）
- [ ] 依赖已安装
- [ ] 本地服务已启动（`http://127.0.0.1:8000`）
- [ ] ngrok/Cloudflare Tunnel 已启动
- [ ] 手机快捷指令已配置
- [ ] 测试通过

---

## 🎉 完成！

现在你可以：
1. ✅ 在本地快速开发和测试
2. ✅ 通过手机快捷指令测试完整流程
3. ✅ 修改代码后立即看到效果
