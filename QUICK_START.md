# 🚀 快速启动指南

## ✅ 当前状态

- ✅ Python 环境：Python 3.9.6
- ✅ 依赖已安装
- ✅ 端口 8000 可用
- ✅ .env 文件已配置（SUPER_MIND_API_KEY）

---

## 📡 启动本地后端

### 方式 1：使用启动脚本（推荐）

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
./scripts/start_local_backend.sh
```

### 方式 2：直接运行

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
python3 app.py
```

### 方式 3：使用 uvicorn（支持热重载）

```bash
cd /Users/lindadexiaoaojiao/Desktop/Builder/AIArchitect/TimeFlow
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

**服务地址**：
- 本地：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- 移动端接口：`http://127.0.0.1:8000/api/mobile/process`

---

## 📱 手机快捷指令配置

### ⚠️ 重要：手机无法直接访问本地服务

需要使用 **ngrok** 或 **Cloudflare Tunnel** 创建公网隧道。

### 步骤 1：安装 ngrok

```bash
# macOS
brew install ngrok/ngrok/ngrok

# 或访问：https://ngrok.com/download
```

### 步骤 2：注册并配置 ngrok

1. 访问：https://dashboard.ngrok.com/signup
2. 注册账号（免费）
3. 获取 authtoken
4. 配置：

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 步骤 3：启动 ngrok 隧道

**在另一个终端窗口**：

```bash
ngrok http 8000
```

你会看到：

```
Forwarding  https://xxxx-xxxx-xxxx.ngrok-free.app -> http://localhost:8000
```

**复制这个 URL**（例如：`https://xxxx-xxxx-xxxx.ngrok-free.app`）

### 步骤 4：配置 iOS 快捷指令

#### 快捷指令名称

`TimeFlow - 语音记录时间`

#### 操作步骤

1. **录制音频**
   ```
   操作：录制音频
   ```

2. **发送到后端**
   ```
   操作：获取 URL 内容
   URL: https://xxxx-xxxx-xxxx.ngrok-free.app/api/mobile/process
   方法: POST
   请求体: 文件
   文件: [录制的音频]
   ```

3. **解析响应**
   ```
   操作：从输入中获取词典值
   键: success
   ```

4. **如果成功**
   ```
   操作：如果
   条件: [success] 等于 true
   ```

5. **获取事件数组**
   ```
   操作：从输入中获取词典值
   键: events
   ```

6. **遍历事件**
   ```
   操作：为每个项目重复
   输入: [events]
   ```

7. **添加日历事件**
   ```
   操作：添加日历事件
   标题: [activity]
   开始时间: [start_time]
   结束时间: [end_time]
   位置: [location]
   备注: [description]
   ```

8. **显示结果**
   ```
   操作：显示通知
   标题: 成功
   内容: 已添加事件到日历
   ```

---

## 🧪 测试

### 本地测试（curl）

```bash
# 测试根路径
curl http://127.0.0.1:8000/

# 测试移动端接口
curl -X POST http://127.0.0.1:8000/api/mobile/process \
  -F "audio_file=@test.m4a"
```

### 通过 ngrok 测试

```bash
# 替换为你的 ngrok URL
curl -X POST https://xxxx-xxxx-xxxx.ngrok-free.app/api/mobile/process \
  -F "audio_file=@test.m4a"
```

### 手机快捷指令测试

1. 打开快捷指令
2. 运行你创建的快捷指令
3. 录制音频（例如："我刚刚吃完饭了，从12点到12点半"）
4. 查看结果

---

## 📋 API 响应格式

### 成功响应

```json
{
  "success": true,
  "transcript": "我刚刚吃完饭了",
  "events": [
    {
      "activity": "吃饭",
      "start_time": "2024-01-30T12:00:00",
      "end_time": "2024-01-30T12:30:00",
      "description": "刚刚吃完饭 [模型: doubao]",
      "location": null,
      "tag": "生活"
    }
  ]
}
```

### 字段说明

- `activity` - 活动名称（必需）
- `start_time` - 开始时间（ISO 8601 格式）
- `end_time` - 结束时间（ISO 8601 格式）
- `description` - 详细描述（可选）
- `location` - 地点（可选）
- `tag` - 标签（可选）

---

## ⚠️ 注意事项

1. **ngrok 免费版限制**：
   - 每次启动 URL 会变化
   - 需要访问验证页面（点击"Visit Site"）
   - 或升级到付费版

2. **Cloudflare Tunnel 替代方案**：
   ```bash
   brew install cloudflared
   cloudflared tunnel --url http://localhost:8000
   ```

3. **服务重启**：
   - 修改代码后需要重启服务
   - 使用 `uvicorn --reload` 可以自动重启

---

## 🎯 下一步

1. ✅ 启动本地服务
2. ✅ 启动 ngrok 隧道
3. ✅ 配置手机快捷指令
4. ✅ 测试完整流程
5. ✅ 根据测试结果优化代码和 Prompt

---

## 📚 相关文档

- [本地设置详细指南](./LOCAL_SETUP_GUIDE.md)
- [手机 API 参考](./MOBILE_API_REFERENCE.md)
- [API 参考](./API_REFERENCE.md)
