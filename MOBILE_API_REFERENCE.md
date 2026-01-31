# 手机快捷指令 API 参考

## 📱 目标流程

1. **手机快捷指令** → 发送录音到云端
2. **云端处理** → 转写 + 分析 → 返回结构化时间块
3. **手机端** → 接收数据 → 写入日历

---

## 🔌 API 端点

### POST `/api/mobile/process`

**用途**：移动端聚合接口，接收音频 → 转写 → 分析 → 返回结构化 events

**请求方式**：`POST`

**Content-Type**：`multipart/form-data`

**请求参数**：
- `audio_file` (File, 可选) - 音频文件
- `file` (File, 可选) - 音频文件（备用字段名）
- `audio` (File, 可选) - 音频文件（备用字段名）
- `recording` (File, 可选) - 音频文件（备用字段名）

**iOS 快捷指令配置**：
- 方法：`POST`
- 请求体：选择"文件"
- 文件：选择"录制的音频"或"快捷指令输入"
- **不要手动设置 Content-Type**（让系统自动带 boundary）

---

## 📤 响应格式

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
      "description": "刚刚吃完饭 [模型: doubao-1-5-lite-32k-250115]",
      "location": "家",
      "tag": "生活",
      "duration_minutes": 30
    }
  ]
}
```

### 失败响应

```json
{
  "success": false,
  "error": "错误信息"
}
```

---

## 📋 结构化时间块字段说明

### 必需字段（Required）

| 字段 | 类型 | 格式 | 说明 | 示例 |
|------|------|------|------|------|
| **`activity`** | string | - | 活动名称（事件标题） | `"吃饭"` |
| **`start_time`** | string | ISO 8601 | 开始时间（24小时制） | `"2024-01-30T12:00:00"` |
| **`end_time`** | string | ISO 8601 | 结束时间（24小时制） | `"2024-01-30T12:30:00"` |

### 可选字段（Optional）

| 字段 | 类型 | 格式 | 说明 | 示例 |
|------|------|------|------|------|
| **`description`** | string | - | 详细描述（包含模型信息） | `"刚刚吃完饭 [模型: doubao]"` |
| **`location`** | string | - | 地点 | `"家"`, `"公司"`, `"咖啡厅"` |
| **`tag`** | string | - | 标签（自动分类） | `"工作"`, `"生活"`, `"娱乐"` |
| **`duration_minutes`** | integer | - | 持续时间（分钟，计算字段） | `30` |

---

## 📅 日历事件字段映射

### Apple Calendar 字段映射

| 云端返回字段 | Apple Calendar 属性 | 说明 |
|-------------|-------------------|------|
| `activity` | `summary` | 事件标题 ✅ |
| `start_time` | `start date` | 开始时间 ✅ |
| `end_time` | `end date` | 结束时间 ✅ |
| `description` | `description` | 事件描述 ✅ |
| `location` | `location` | 事件地点 ✅ |
| `tag` | `calendar_name` | 日历名称（标签）✅ |

---

## 🔄 手机端处理流程

### 步骤 1：发送录音

```javascript
// iOS 快捷指令示例
POST https://your-domain.ai-builders.space/api/mobile/process
Content-Type: multipart/form-data

audio_file: [录制的音频文件]
```

### 步骤 2：接收响应

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
      "location": "家",
      "tag": "生活"
    }
  ]
}
```

### 步骤 3：写入日历

**iOS 快捷指令操作**：
1. 解析 JSON 响应
2. 遍历 `events` 数组
3. 对每个事件：
   - 使用"添加日历事件"操作
   - 标题：`activity`
   - 开始时间：`start_time`
   - 结束时间：`end_time`
   - 位置：`location`（如果有）
   - 备注：`description`（如果有）
   - 日历：根据 `tag` 选择对应日历（如"工作"、"生活"）

---

## 📝 iOS 快捷指令配置示例

### 1. 录制音频

```
操作：录制音频
```

### 2. 发送到云端

```
操作：获取 URL 内容
URL: https://your-domain.ai-builders.space/api/mobile/process
方法: POST
请求体: 文件
文件: [录制的音频]
```

### 3. 解析响应

```
操作：从输入中获取词典值
键: events
```

### 4. 遍历事件

```
操作：为每个项目重复
输入: [events 数组]
```

### 5. 添加日历事件

```
操作：添加日历事件
标题: [activity]
开始时间: [start_time]
结束时间: [end_time]
位置: [location]
备注: [description]
日历: [根据 tag 选择]
```

---

## 🎯 完整示例

### 输入（录音）

```
"我刚刚吃完饭了，从12点到12点半"
```

### 云端处理

1. **转写**：`"我刚刚吃完饭了，从12点到12点半"`
2. **分析**：提取时间块
3. **返回**：

```json
{
  "success": true,
  "transcript": "我刚刚吃完饭了，从12点到12点半",
  "events": [
    {
      "activity": "吃饭",
      "start_time": "2024-01-30T12:00:00",
      "end_time": "2024-01-30T12:30:00",
      "description": "刚刚吃完饭 [模型: doubao-1-5-lite-32k-250115]",
      "location": null,
      "tag": "生活",
      "duration_minutes": 30
    }
  ]
}
```

### 手机端写入日历

- **标题**：吃饭
- **开始时间**：2024-01-30 12:00:00
- **结束时间**：2024-01-30 12:30:00
- **位置**：（空）
- **备注**：刚刚吃完饭 [模型: doubao-1-5-lite-32k-250115]
- **日历**：生活

---

## 🔍 字段详细说明

### `activity` (活动名称)

- **类型**：string
- **必需**：是
- **说明**：从语音中提取的活动名称
- **示例**：`"吃饭"`, `"开会"`, `"学习"`, `"通勤"`

### `start_time` (开始时间)

- **类型**：string
- **格式**：ISO 8601 (`YYYY-MM-DDTHH:MM:SS`)
- **必需**：是
- **说明**：24小时制时间格式
- **示例**：`"2024-01-30T12:00:00"`

### `end_time` (结束时间)

- **类型**：string
- **格式**：ISO 8601 (`YYYY-MM-DDTHH:MM:SS`)
- **必需**：是
- **说明**：24小时制时间格式
- **示例**：`"2024-01-30T12:30:00"`

### `description` (详细描述)

- **类型**：string
- **必需**：否
- **说明**：包含原始文本或额外信息，末尾会添加模型信息
- **示例**：`"刚刚吃完饭 [模型: doubao-1-5-lite-32k-250115]"`

### `location` (地点)

- **类型**：string
- **必需**：否
- **说明**：从语音中提取的地点信息
- **示例**：`"家"`, `"公司"`, `"咖啡厅"`, `null`

### `tag` (标签)

- **类型**：string
- **必需**：否
- **说明**：自动分类的标签（工作/生活/娱乐）
- **示例**：`"工作"`, `"生活"`, `"娱乐"`

### `duration_minutes` (持续时间)

- **类型**：integer
- **必需**：否
- **说明**：计算字段，从 start_time 和 end_time 计算得出
- **示例**：`30`

---

## ⚠️ 注意事项

### 1. 时间格式

- 所有时间字段使用 **ISO 8601** 格式
- 24小时制
- 时区：UTC（或本地时区，取决于部署配置）

### 2. 多个时间块

- `events` 是**数组**，可能包含多个时间块
- 手机端需要遍历数组，为每个事件创建日历条目

### 3. 可选字段处理

- `location`、`description`、`tag` 可能为 `null`
- 手机端需要检查字段是否存在再使用

### 4. 错误处理

- 检查 `success` 字段
- 如果 `success: false`，显示 `error` 信息

---

## 🧪 测试示例

### 测试请求

```bash
curl -X POST https://your-domain.ai-builders.space/api/mobile/process \
  -F "audio_file=@test.m4a"
```

### 测试响应

```json
{
  "success": true,
  "transcript": "我刚刚吃完饭了",
  "events": [
    {
      "activity": "吃饭",
      "start_time": "2024-01-30T12:00:00",
      "end_time": "2024-01-30T12:30:00",
      "description": "刚刚吃完饭 [模型: doubao-1-5-lite-32k-250115]",
      "location": null,
      "tag": "生活"
    }
  ]
}
```

---

## 📚 相关文档

- [API 参考](./API_REFERENCE.md) - 完整的 API 列表和优先级
- [Apple Calendar 字段](./MacApp/APPLE_CALENDAR_FIELDS.md) - 日历字段详细说明
- [部署指南](./DEPLOYMENT_UPDATE_GUIDE.md) - 云端部署说明

---

## ✅ 总结

### 必需字段（3个）

1. ✅ `activity` - 活动名称
2. ✅ `start_time` - 开始时间（ISO 8601）
3. ✅ `end_time` - 结束时间（ISO 8601）

### 可选字段（4个）

4. ⭐ `description` - 详细描述
5. ⭐ `location` - 地点
6. ⭐ `tag` - 标签（自动分类）
7. ⭐ `duration_minutes` - 持续时间（计算字段）

### 手机端需要做的

1. ✅ 发送录音到 `/api/mobile/process`
2. ✅ 解析 JSON 响应
3. ✅ 遍历 `events` 数组
4. ✅ 为每个事件创建日历条目
5. ✅ 映射字段到日历属性
