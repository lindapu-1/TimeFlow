# 📅 Apple Calendar 字段调研

## 🎯 调研目标

确定写入 Apple 日历需要哪些字段，以便：
1. 确认 AI 模型需要从转写文本中提取哪些信息
2. 优化数据结构设计
3. 完善 AppleScript 实现

---

## 📋 Apple Calendar 事件属性（完整列表）

### ✅ 必需字段（Required）

| 字段 | AppleScript 属性 | 类型 | 说明 | 当前实现 |
|------|-----------------|------|------|---------|
| **开始时间** | `start date` | date | 事件开始时间 | ✅ 已实现 |
| **结束时间** | `end date` | date | 事件结束时间 | ✅ 已实现 |
| **标题** | `summary` | string | 事件标题/名称 | ✅ 已实现（activity） |

### 📝 可选字段（Optional）

| 字段 | AppleScript 属性 | 类型 | 说明 | 当前实现 | 建议提取 |
|------|-----------------|------|------|---------|---------|
| **描述** | `description` | string | 事件详细描述 | ✅ 已实现（status） | ⭐ 建议提取 |
| **地点** | `location` | string | 事件地点 | ❌ 未实现 | ⭐ 建议提取 |
| **全天事件** | `allday event` | boolean | 是否为全天事件 | ❌ 未实现 | 可提取 |
| **URL** | `url` | string | 相关链接 | ❌ 未实现 | 可提取 |
| **重复规则** | `recurrence` | string | 重复规则 | ❌ 未实现 | 可提取 |
| **状态** | `status` | enum | 事件状态 | ❌ 未实现 | 已提取（但未使用） |
| **时间戳** | `stamp date` | date | 创建时间 | ❌ 自动生成 | - |
| **序列号** | `sequence` | integer | 版本号 | ❌ 自动生成 | - |

---

## 🔍 实际测试结果

### 测试命令
```applescript
tell application "Calendar"
  make new event at end of calendar 1 with properties {
    summary: "Test",
    start date: (current date),
    end date: (current date) + 3600
  }
end tell
```

### 返回的属性
```
id, recurrence, stamp date, class, url, end date, 
excluded dates, description, summary, location, 
allday event, start date, sequence, status
```

---

## 💡 建议的数据结构

### 当前数据结构（已实现）

```json
{
  "activity": "活动名称",           // → summary
  "start_time": "2024-01-01T09:00:00",  // → start date
  "end_time": "2024-01-01T11:00:00",    // → end date
  "duration_minutes": 120,         // 计算字段
  "status": "completed"            // → description
}
```

### 建议扩展的数据结构

```json
{
  "activity": "活动名称",           // → summary (必需)
  "start_time": "2024-01-01T09:00:00",  // → start date (必需)
  "end_time": "2024-01-01T11:00:00",    // → end date (必需)
  "duration_minutes": 120,         // 计算字段
  "status": "completed",          // → description
  "location": "地点",              // → location (新增)
  "description": "详细描述",        // → description (扩展)
  "allday": false,                 // → allday event (新增)
  "url": "https://..."             // → url (新增，可选)
}
```

---

## 🤖 AI 模型需要提取的字段

### 必需字段（必须提取）

1. **activity** (活动名称)
   - 从文本中提取：用户在做什么
   - 示例："我刚刚吃完饭了" → "吃饭"
   - 映射到：`summary`

2. **start_time** (开始时间)
   - 从文本中提取：活动开始时间
   - 示例："9点到11点" → "09:00"
   - 映射到：`start date`

3. **end_time** (结束时间)
   - 从文本中提取：活动结束时间
   - 示例："9点到11点" → "11:00"
   - 映射到：`end date`

### 建议提取的字段（增强体验）

4. **location** (地点) ⭐
   - 从文本中提取：活动地点
   - 示例："我在公司开会" → "公司"
   - 示例："在家吃饭" → "家"
   - 映射到：`location`

5. **description** (详细描述) ⭐
   - 从文本中提取：活动详细描述
   - 可以包含：原始文本、额外信息
   - 映射到：`description`

6. **allday** (全天事件)
   - 从文本中判断：是否为全天事件
   - 示例："今天一整天都在开会" → true
   - 映射到：`allday event`

### 计算字段（不需要提取）

- **duration_minutes**: 从 start_time 和 end_time 计算
- **status**: 从时间判断（completed/ongoing/planned）

---

## 📝 更新的 AI 提示词建议

### 当前提示词（已实现）
```
提取：activity, start_time, end_time, duration_minutes, status
```

### 建议扩展的提示词

```
提取以下信息：
1. activity (活动名称) - 必需
2. start_time (开始时间) - 必需
3. end_time (结束时间) - 必需
4. location (地点) - 可选，如果提到地点则提取
5. description (详细描述) - 可选，可以包含原始文本或额外信息
6. allday (全天事件) - 可选，如果提到"整天"、"全天"等
7. duration_minutes (持续时间) - 计算字段
8. status (状态) - 从时间判断
```

---

## 🔧 实现建议

### 1. 更新数据结构

在 `app.py` 中扩展 `TimeEntry` 模型：

```python
class TimeEntry(BaseModel):
    activity: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: str  # completed, ongoing, planned
    location: Optional[str] = None  # 新增
    description: Optional[str] = None  # 扩展
    allday: Optional[bool] = False  # 新增
```

### 2. 更新 AppleScript

在 `main.js` 中扩展 `addToCalendar` 函数：

```javascript
make new event at end with properties {
  summary: "${escapedActivity}",
  start date: date "${formatDate(startDate)}",
  end date: date "${formatDate(endDate)}",
  description: "${escapedDescription}",
  location: "${escapedLocation}",
  allday event: ${eventData.allday || false}
}
```

### 3. 更新 AI 提示词

在 `app.py` 中扩展系统提示词，让 AI 提取更多信息。

---

## ✅ 优先级建议

### 高优先级（立即实现）
1. ✅ **summary** (activity) - 已实现
2. ✅ **start date** (start_time) - 已实现
3. ✅ **end date** (end_time) - 已实现
4. ⭐ **location** - 建议添加（提升用户体验）

### 中优先级（后续优化）
5. ⭐ **description** - 建议扩展（当前只有 status）
6. **allday event** - 可选（如果用户经常提到全天事件）

### 低优先级（可选）
7. **url** - 很少用到
8. **recurrence** - 复杂，需要特殊处理

---

## 📊 总结

### 必需字段（3个）
- ✅ summary (activity)
- ✅ start date (start_time)
- ✅ end date (end_time)

### 建议添加（2个）
- ⭐ location (地点)
- ⭐ description (详细描述，扩展当前实现)

### 当前实现状态
- ✅ 基础功能已实现
- ⭐ 建议添加 location 字段
- ⭐ 建议扩展 description 字段

---

## 🎯 下一步行动

1. **更新 AI 提示词**：添加 location 和 description 提取
2. **更新数据结构**：在 `TimeEntry` 中添加 location 字段
3. **更新 AppleScript**：在创建事件时添加 location 和 description
4. **测试验证**：测试新字段的提取和写入




