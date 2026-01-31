#!/usr/bin/env python3
"""
TimeFlow MVP - 语音时间记录应用
FastAPI 后端服务
"""
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, List
import logging
import httpx
import tempfile
import subprocess
import re
from collections import Counter
import re


def normalize_transcript_text(text: str) -> str:
    """
    规范化转写文本显示：
    - 去掉中文字符之间的多余空格（如“今 天 下 午”->“今天下午”）
    - 规范标点前空格
    - 合并多空格
    """
    if not text:
        return ""
    t = str(text).strip()
    # 合并空白
    t = re.sub(r"\s+", " ", t)
    # 去掉中文字符之间的空格
    t = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", t)
    # 去掉标点前的空格
    t = re.sub(r"\s+([，。！？；：,.!?;:])", r"\1", t)
    return t.strip()


def escape_html(text: str) -> str:
    """将纯文本转为适合 Apple Notes body 的安全 HTML（最小化转义 + 换行）"""
    if text is None:
        return ""
    t = str(text)
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\n", "<br>")
    return t


def format_note_entry(event: dict) -> str:
    """
    按用户期望格式生成一条备忘录记录：
    MM-DD HH:MM-HH:MM
    活动名称
    """
    start_time = event.get("start_time")
    end_time = event.get("end_time")
    activity = (event.get("activity") or "").strip()

    def _fmt(iso: Optional[str], with_date: bool) -> str:
        if not iso:
            return ""
        try:
            dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone().replace(tzinfo=None)
            if with_date:
                return dt.strftime("%m-%d %H:%M")
            return dt.strftime("%H:%M")
        except Exception:
            return str(iso)

    left = _fmt(start_time, True)
    right = _fmt(end_time, False)
    header = f"{left}-{right}".strip("-")
    return f"{header}\n{activity}".strip()


def append_to_notes_via_applescript(note_name: str, text_to_append: str) -> dict:
    """
    追加文本到 Apple Notes 的指定备忘录（按“名称”匹配）。
    - 若找不到同名备忘录，则在第一个账户的第一个文件夹创建
    - Notes 的 body 是 HTML，这里会把换行转成 <br>
    """
    try:
        if not note_name:
            note_name = "时间"
        if not text_to_append:
            return {"success": True, "message": "无需写入备忘录（内容为空）"}

        note_name_escaped = escape_apple_script(note_name)
        html_body = escape_html(text_to_append)
        html_body_escaped = escape_apple_script(html_body)

        commands = [
            'tell application "Notes"',
            'set targetNote to missing value',
            'set targetFolder to missing value',
            'set targetAccount to missing value',
            'if (count of accounts) = 0 then error "未找到 Notes 账户"',
            'set targetAccount to item 1 of accounts',
            'if (count of folders of targetAccount) = 0 then error "未找到 Notes 文件夹"',
            'set targetFolder to item 1 of folders of targetAccount',
            'repeat with acc in accounts',
            'repeat with fol in folders of acc',
            'repeat with n in notes of fol',
            f'if name of n is "{note_name_escaped}" then set targetNote to n',
            'if targetNote is not missing value then exit repeat',
            'end repeat',
            'if targetNote is not missing value then exit repeat',
            'end repeat',
            'if targetNote is not missing value then exit repeat',
            'end repeat',
            'if targetNote is missing value then',
            f'set targetNote to make new note at targetFolder with properties {{name:"{note_name_escaped}", body:""}}',
            'end if',
            'set oldBody to body of targetNote',
            f'set newBody to oldBody & "<br><br>{html_body_escaped}"',
            'set body of targetNote to newBody',
            'return "success"',
            'end tell',
        ]

        escaped_commands = [c.replace("'", "'\\''") for c in commands]
        cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"success": False, "error": (result.stderr or result.stdout or "Notes AppleScript 执行失败").strip()}
        return {"success": True, "message": "已追加到备忘录"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "写入备忘录超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Faster Whisper (可选，如果安装了)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logger.warning("Faster Whisper 未安装，本地转录功能不可用。安装: pip install faster-whisper")

# 加载环境变量
load_dotenv()

app = FastAPI(title="TimeFlow MVP")

# 配置 CORS（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 OpenAI 客户端（用于 AI Builder API）
api_key = os.getenv("SUPER_MIND_API_KEY") or os.getenv("AI_BUILDER_TOKEN")
if not api_key:
    raise ValueError("请设置 SUPER_MIND_API_KEY 或 AI_BUILDER_TOKEN 环境变量")

# 初始化 OpenAI 客户端（用于 AI Builder API）
# 使用 httpx 客户端来避免版本兼容问题
import httpx
client = OpenAI(
    api_key=api_key,
    base_url="https://space.ai-builders.com/backend/v1",
    http_client=httpx.Client()
)

# API 配置
TRANSCRIPTION_API_URL = "https://space.ai-builders.com/backend/v1/audio/transcriptions"
TIME_LOG_FILE = "data/time_log.json"
RECENT_EVENT_FILE = "data/recent_event.json"  # 存储最近写入的事件信息（用于快速撤回）
EVENT_HISTORY_FILE = "data/event_history.json"  # 存储所有历史事件记录（每次操作 append）
TAGS_FILE = "data/tags.json"  # 存储标签配置（用户自定义标签）

# 确保数据目录存在
os.makedirs("data", exist_ok=True)

# Faster Whisper 模型（懒加载，备用）
whisper_model = None
# 根据基准测试，tiny 是最快的模型（0.3秒），推荐用于实时场景
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")  # tiny, base, small, medium, large
USE_LOCAL_STT = os.getenv("USE_LOCAL_STT", "false").lower() == "true"  # 是否使用本地 STT（Faster Whisper）

# Ollama 配置
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
# 根据基准测试，llama3.2:latest 是最快的本地模型（3秒），多时间块提取准确
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"

# 豆包云端模型配置（根据基准测试，doubao-1-5-lite-32k-250115 是最佳模型：2.79秒，95.2%准确率）
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")  # 必须从环境变量读取，不要硬编码
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-seed-1-6-251015")
USE_DOUBAO = os.getenv("USE_DOUBAO", "true").lower() == "true"  # 默认使用豆包模型

# 如果使用豆包模型但未提供 API key，给出警告（不强制，因为可能使用其他模型）
if USE_DOUBAO and not DOUBAO_API_KEY:
    logger.warning("⚠️  DOUBAO_API_KEY 未设置，豆包模型将不可用")


def get_whisper_model():
    """懒加载 Whisper 模型"""
    global whisper_model
    if whisper_model is None and FASTER_WHISPER_AVAILABLE:
        try:
            logger.info(f"加载 Faster Whisper 模型: {WHISPER_MODEL_SIZE}")
            whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
            logger.info("✅ Faster Whisper 模型加载成功")
        except Exception as e:
            logger.error(f"❌ Faster Whisper 模型加载失败: {e}")
            whisper_model = None
    return whisper_model


# Prompt 模板缓存
_system_prompt_template = None
_user_prompt_template = None


def load_prompts_from_file():
    """从 prompts.md 文件加载 prompt 模板"""
    global _system_prompt_template, _user_prompt_template
    
    if _system_prompt_template is not None and _user_prompt_template is not None:
        return _system_prompt_template, _user_prompt_template
    
    prompt_file = "prompts.md"
    if not os.path.exists(prompt_file):
        logger.warning(f"Prompt 文件 {prompt_file} 不存在，使用默认 prompt")
        return None, None
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 System Prompt（在 "## System Prompt" 和 "---" 之间的代码块）
        system_match = re.search(
            r'## System Prompt.*?```markdown\n(.*?)```',
            content,
            re.DOTALL
        )
        if system_match:
            _system_prompt_template = system_match.group(1).strip()
            logger.info("✅ 已加载 System Prompt 模板")
        else:
            logger.warning("未找到 System Prompt，使用默认 prompt")
        
        # 提取 User Prompt（在 "## User Prompt" 和 "---" 之间的代码块）
        user_match = re.search(
            r'## User Prompt.*?```markdown\n(.*?)```',
            content,
            re.DOTALL
        )
        if user_match:
            _user_prompt_template = user_match.group(1).strip()
            logger.info("✅ 已加载 User Prompt 模板")
        else:
            logger.warning("未找到 User Prompt，使用默认 prompt")
        
        return _system_prompt_template, _user_prompt_template
    
    except Exception as e:
        logger.error(f"加载 Prompt 文件失败: {e}")
        return None, None


def get_system_prompt(current_time_str: str) -> str:
    """获取格式化后的 System Prompt（动态加载标签信息）"""
    template, _ = load_prompts_from_file()
    
    # 加载标签配置，生成标签分类规则
    tags_config = load_tags_config()
    tags = tags_config.get("tags", [])
    
    # 构建标签分类规则文本（只使用描述）
    tag_rules = []
    tag_list = []
    for tag in tags:
        tag_name = tag.get("name", "")
        tag_desc = tag.get("description", "")
        if tag_name:
            tag_list.append(tag_name)
            if tag_desc:
                tag_rules.append(f"- **{tag_name}**：{tag_desc}")
            else:
                tag_rules.append(f"- **{tag_name}**")
    
    tag_rules_text = "\n".join(tag_rules)
    tag_list_text = "、".join(tag_list) if tag_list else "工作、生活、娱乐、运动"
    
    if template is None:
        # Fallback to default hardcoded prompt（使用动态标签）
        return f"""你是一个时间提取助手。从用户提供的文本中提取时间相关的信息，并返回 JSON 格式的数据。你需要根据用户的描述，帮助用户记录时间，提取出时间块（duration），包括开始时间和结束时间。在两个时间点中间，可能需要一定的适当推理得出这块时间在做什么。

**重要提示**：
1. 一条文本可能包含多个时间块，必须全部提取，不要遗漏任何时间段
2. 对于相对时间（如"刚刚"、"刚才"、"半小时前"），必须根据当前时间进行推理，这些是过去的时间
3. 当前时间：{current_time_str}（格式：YYYY-MM-DD HH:MM:SS，24小时制）

需要提取的字段（每个时间块）：
1. **activity** (活动名称) - 必需，从文本中提取用户在做什么
2. **start_time** (开始时间) - 必需，格式：YYYY-MM-DDTHH:MM:SS（ISO 8601，24小时制），如果文本中没有明确时间，根据当前时间和相对时间推断
3. **end_time** (结束时间) - 必需，格式：YYYY-MM-DDTHH:MM:SS（ISO 8601，24小时制），如果文本中没有明确时间，根据当前时间和相对时间推断
4. **location** (地点) - 可选，如果文本中提到地点则提取
5. **description** (详细描述) - 可选，可以包含原始文本或额外信息
6. **tag** (标签分类) - 必需，根据活动内容自动分类为以下标签之一：**{tag_list_text}**

**标签分类规则**：
{tag_rules_text}

**标签判断方法**：
- 根据 activity 和 description 的内容，结合标签描述进行判断
- 如果活动同时匹配多个标签，选择最匹配的一个
- 如果无法确定，默认使用"生活"

**严格格式要求**：
- 只返回 JSON 数组，不要有任何其他文字
- 不要使用 markdown 代码块
- 不要添加任何解释或说明
- 直接以 [ 开始，以 ] 结束

**处理规则**：
1. **多个时间块（重要！必须全部提取）**：
   - 如果文本包含多个连续时间段，必须全部提取，不要遗漏任何时间段
   - 示例："今天早上八点出门然后九点到了咖啡厅九点到九点半呢我开始学习"
     → 必须提取两个时间块：
     - 时间块1：08:00-09:00，activity="通勤/去咖啡厅"，location="咖啡厅"
     - 时间块2：09:00-09:30，activity="学习"，location="咖啡厅"
   - 不要遗漏通勤、移动、准备等时间段
   - 如果文本提到"8点...然后9点..."，必须提取8-9点这个时间段

2. **时间格式（24小时制）**：
   - 必须使用 24 小时制（00:00-23:59）
   - "早上8点" = 08:00
   - "晚上8点" = 20:00（不是08:00）
   - "晚上九点" = 21:00
   - 如果文本说"晚上八点到九点"，开始时间是 20:00，结束时间是 21:00

3. **相对时间（过去的时间，重要！）**：
   - "刚刚"、"刚才" = 刚刚结束，结束时间是当前时间
   - "刚刚半小时" = 开始时间：当前时间减去30分钟，结束时间：当前时间（这是过去的时间，不是未来）
   - "半小时前" = 开始时间：当前时间减去30分钟，结束时间：当前时间
   - 重要：相对时间都是过去的时间，结束时间必须是当前时间（{current_time_str}），不是未来时间
   - 计算方式：如果当前时间是 {current_time_str}，"刚刚半小时"的结束时间必须是 {current_time_str}，开始时间是 {current_time_str} 减去30分钟
   - 错误示例：如果当前时间是 10:33，"刚刚半小时" ≠ 09:30-10:00（这是过去的时间段，不是"刚刚"）
   - 正确示例：如果当前时间是 10:33，"刚刚半小时" = 10:03-10:33（结束时间是当前时间）

4. **时间推断**：
   - 如果文本没有明确时间，根据上下文和当前时间合理推断
   - 如果提到"今天早上"、"今天晚上"，使用当前日期
   - 如果只提到时间点（如"8点"），根据上下文判断是早上还是晚上

5. **地点提取**：如果文本提到地点（如"在公司"、"在家"、"咖啡厅"），提取到 location 字段

6. **避免过度分割**：只提取有意义的时间块，不要将"到达"、"开始"等瞬间动作单独提取。但如果文本明确提到多个时间段，必须全部提取"""
    
    # 如果模板中包含 {tag_rules} 或 {tag_list}，替换它们
    if template:
        template = template.replace("{tag_rules}", tag_rules_text)
        template = template.replace("{tag_list}", tag_list_text)
    
    return template.format(current_time_str=current_time_str)


def get_user_prompt(transcript: str, current_time_str: str, current_time_iso: str, 
                     current_dt: datetime, past_30min_str: str) -> str:
    """获取格式化后的 User Prompt"""
    _, template = load_prompts_from_file()
    
    # 预先计算日期字符串（避免在模板中使用 Python 代码）
    current_date_str = current_dt.strftime('%Y-%m-%d')
    
    if template is None:
        # 使用默认 prompt（向后兼容）
        return f"""从以下文本中提取时间信息，只返回 JSON 数组，不要有任何其他文字：

文本：{transcript}

当前时间：{current_time_str}（ISO格式：{current_time_iso}）

**提取思路（两步法）**：
1. **第一步：提取所有时间点**
   - 从文本中找出所有明确提到的时间点（如"8点"、"9点"、"9点半"）
   - 对于相对时间（如"刚刚"、"半小时前"），根据当前时间计算具体时间点
   
2. **第二步：推断时间点之间的事件**
   - 相邻两个时间点之间就是一个时间段
   - 根据文本内容推断这个时间段内发生了什么事件
   - 提取事件的活动名称、地点等信息

**示例说明**：
- 示例1：文本"今天早上八点出门然后九点到了咖啡厅九点到九点半呢我开始学习"
  - 时间点：8点，9点，9点半
  - 时间段1（8点-9点）：通勤/去咖啡厅，地点：咖啡厅
  - 时间段2（9点-9点半）：学习，地点：咖啡厅
  - 结果：[{{"activity": "通勤/去咖啡厅", "start_time": "{current_date_str}T08:00:00", "end_time": "{current_date_str}T09:00:00", "location": "咖啡厅"}},
         {{"activity": "学习", "start_time": "{current_date_str}T09:00:00", "end_time": "{current_date_str}T09:30:00", "location": "咖啡厅"}}]

- 示例2：文本"刚刚半小时我在吃饭"
  - 时间点：半小时前（{past_30min_str}），现在（{current_time_iso}）
  - 时间段（半小时前-现在）：吃饭
  - 结果：[{{"activity": "吃饭", "start_time": "{past_30min_str}", "end_time": "{current_time_iso}", "location": null}}]

**重要提示**：
1. **多个时间段必须全部提取**：如果文本提到多个时间点，必须提取所有相邻时间段，不要遗漏
2. **相对时间计算**：相对时间的结束时间必须是当前时间（{current_time_iso}），不是未来时间

只返回 JSON 数组，格式：[{{"activity": "...", "start_time": "...", "end_time": "...", "location": "..."}}]"""
    
    # 替换模板变量
    # 注意：模板中使用 {transcript} 而不是 {request.transcript}
    # 如果模板中有 {current_dt.strftime('%Y-%m-%d')}，需要先替换为计算好的日期字符串
    if template and '{current_dt.strftime' in template:
        # 替换模板中的 Python 代码为实际值
        template = template.replace('{current_dt.strftime(\'%Y-%m-%d\')}', current_date_str)
    
    return template.format(
        transcript=transcript,
        current_time_str=current_time_str,
        current_time_iso=current_time_iso,
        current_dt=current_dt,
        past_30min_str=past_30min_str,
        current_date=current_date_str  # 添加预计算的日期字符串
    )


# 数据模型
class ChatRequest(BaseModel):
    messages: List[dict]
    model: Optional[str] = "supermind-agent-v1"


class TimeAnalysisRequest(BaseModel):
    """时间分析请求"""
    transcript: str  # 转录文本
    use_ollama: Optional[bool] = False  # 是否使用 Ollama


class TimeEntry(BaseModel):
    """时间记录条目"""
    activity: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = "completed"
    description: Optional[str] = None
    location: Optional[str] = None


class CalendarEventRequest(BaseModel):
    """日历事件请求"""
    activity: str
    start_time: str
    end_time: str
    description: Optional[str] = None
    location: Optional[str] = None
    calendar_name: Optional[str] = None  # 日历名称（标签），默认使用 "TimeFlow"
    tag: Optional[str] = None  # 标签名称（用于前端显示）
    recurrence: Optional[str] = None  # 重复规则: "daily", "weekly", "monthly", "yearly"
    note_name: Optional[str] = None  # 备忘录名称（默认“时间”）


# 工具函数
def escape_apple_script(text):
    """转义 AppleScript 特殊字符"""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def load_tags_config() -> dict:
    """加载标签配置"""
    if os.path.exists(TAGS_FILE):
        try:
            with open(TAGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载标签配置失败: {e}，使用默认配置")
    
    # 返回默认配置
    return {
        "tags": [
            {"id": "work", "name": "工作", "description": "工作相关活动", "color": "#FF6B6B", "is_default": True},
            {"id": "life", "name": "生活", "description": "日常生活活动", "color": "#95E1D3", "is_default": True},
            {"id": "entertainment", "name": "娱乐", "description": "娱乐休闲活动", "color": "#F38181", "is_default": True},
            {"id": "sports", "name": "运动", "description": "运动健身活动", "color": "#AA96DA", "is_default": True}
        ]
    }


def get_tag_by_name(tag_name: str) -> dict:
    """根据标签名称获取标签信息（包括颜色）"""
    tags_config = load_tags_config()
    for tag in tags_config.get("tags", []):
        if tag.get("name") == tag_name:
            return tag
    # 如果找不到，返回默认标签
    return {"id": "life", "name": "生活", "color": "#95E1D3"}


def classify_activity_tag(activity: str, description: str = "") -> str:
    """
    根据活动内容自动分类标签（仅作为后备，主要依赖 LLM 分类）
    
    注意：现在分类主要依赖 LLM 根据 prompt 中的标签描述进行判断。
    此函数仅作为后备方案，当 LLM 没有返回有效标签时使用。
    
    Args:
        activity: 活动名称
        description: 活动描述
    
    Returns:
        标签名称（默认返回"生活"）
    """
    # 现在完全依赖 LLM 的分类，这里只返回默认值
    # 如果需要，可以根据描述进行简单的文本匹配，但主要应该依赖 LLM
    return "生活"  # 默认标签


def save_recent_events(event_ids: List[str], events_data: List[dict]):
    """保存最近写入的多个事件信息（一次操作可能写入多个事件）
    同时保存到历史记录文件（append）和最近事件文件（覆盖）
    """
    events_info = {
        "event_ids": event_ids,  # 多个事件ID
        "events": events_data,  # 多个事件的完整数据
        "created_at": datetime.now().isoformat(),
        "count": len(event_ids)
    }
    
    try:
        # 1. 保存到最近事件文件（用于快速撤回）
        with open(RECENT_EVENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(events_info, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存最近 {len(event_ids)} 个事件信息")
        
        # 2. 追加到历史记录文件（保留所有操作历史）
        history_entry = {
            "id": f"op_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(event_ids)}",
            **events_info
        }
        
        # 读取现有历史记录
        if os.path.exists(EVENT_HISTORY_FILE):
            with open(EVENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = {"operations": []}
        
        # 追加新操作到开头（最新的在前面）
        history["operations"].insert(0, history_entry)
        
        # 保存历史记录
        with open(EVENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info(f"已追加到历史记录，共 {len(history['operations'])} 次操作")
        
    except Exception as e:
        logger.warning(f"保存事件信息失败: {e}")


def hex_to_rgb(hex_color: str) -> tuple:
    """将十六进制颜色转换为 RGB 元组 (0-65535)"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # AppleScript 使用 0-65535 范围的 RGB
        return (r * 257, g * 257, b * 257)
    return (49152, 49152, 49152)  # 默认灰色


def add_to_calendar_via_applescript(event_data: dict) -> dict:
    """使用 AppleScript 添加到苹果日历，返回事件ID"""
    activity = event_data.get('activity', '未命名活动')
    start_time = event_data.get('start_time')
    end_time = event_data.get('end_time')
    description = event_data.get('description', '') or event_data.get('location', '')
    calendar_name = event_data.get('calendar_name', 'TimeFlow')  # 默认使用 TimeFlow
    recurrence = event_data.get('recurrence')  # 重复规则
    tag_color = event_data.get('tag_color')  # 标签颜色（十六进制，如 #FF6B6B）
    
    # 转义特殊字符
    escaped_activity = escape_apple_script(activity)
    escaped_description = escape_apple_script(description)
    escaped_calendar = escape_apple_script(calendar_name)
    
    # 格式化日期
    if start_time:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if start_dt.tzinfo:
            start_dt = start_dt.replace(tzinfo=None)
        now_dt = datetime.now()
        start_seconds = int((start_dt - now_dt).total_seconds())
    else:
        start_seconds = 0
    
    if end_time:
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        if end_dt.tzinfo:
            end_dt = end_dt.replace(tzinfo=None)
        now_dt = datetime.now()
        end_seconds = int((end_dt - now_dt).total_seconds())
    else:
        end_seconds = start_seconds + 3600
    
    # 构建 AppleScript 命令（创建事件并返回事件ID）
    commands = [
        'tell application "Calendar"',
        'activate',
        f'set calendarName to "{escaped_calendar}"',
        'try',
        f'set targetCalendar to calendar calendarName',
        'on error',
        f'make new calendar with properties {{name:calendarName}}',
        f'set targetCalendar to calendar calendarName',
        'end try'
    ]
    
    # 如果提供了标签颜色，设置日历颜色
    if tag_color:
        try:
            r, g, b = hex_to_rgb(tag_color)
            commands.append(f'set color of targetCalendar to {{{r}, {g}, {b}}}')
            logger.info(f"设置日历颜色: {calendar_name} -> {tag_color} (RGB: {r}, {g}, {b})")
        except Exception as e:
            logger.warning(f"设置日历颜色失败: {e}")
    
    commands.extend([
        'tell targetCalendar',
        f'make new event at end with properties {{summary:"{escaped_activity}", start date:(current date) + {start_seconds}, end date:(current date) + {end_seconds}, description:"{escaped_description}"}}',
        'set newEvent to result'
    ])
    
    # 添加重复规则（如果指定）
    if recurrence:
        if recurrence == "daily":
            commands.append('set recurrence of newEvent to "FREQ=DAILY;INTERVAL=1"')
        elif recurrence == "weekly":
            commands.append('set recurrence of newEvent to "FREQ=WEEKLY;INTERVAL=1"')
        elif recurrence == "monthly":
            commands.append('set recurrence of newEvent to "FREQ=MONTHLY;INTERVAL=1"')
        elif recurrence == "yearly":
            commands.append('set recurrence of newEvent to "FREQ=YEARLY;INTERVAL=1"')
    
    commands.extend([
        'set eventId to id of newEvent',
        'return eventId',
        'end tell',
        'end tell'
    ])
    
    # 转义单引号
    escaped_commands = [c.replace("'", "'\\''") for c in commands]
    
    # 使用多个 -e 参数执行 AppleScript
    cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            event_id = result.stdout.strip()
            return {"success": True, "event_id": event_id, "message": "事件已添加到日历"}
        else:
            return {"success": False, "error": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "AppleScript 执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def undo_last_events_via_applescript() -> dict:
    """撤回最近写入的多个日历事件（一次操作的所有事件）
    从历史记录中删除最近一次操作，并更新最近事件文件
    """
    # 优先从历史记录读取（更可靠）
    if os.path.exists(EVENT_HISTORY_FILE):
        try:
            with open(EVENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            operations = history.get("operations", [])
            if not operations:
                return {"success": False, "error": "历史记录为空"}
            
            # 获取最近一次操作
            last_operation = operations[0]
            event_ids = last_operation.get("event_ids", [])
            events_data = last_operation.get("events", [])
            
            if not event_ids:
                return {"success": False, "error": "事件ID列表为空"}
            
            # 逐个删除事件，记录每个事件的删除状态
            delete_results = []
            for i, (event_id, event_data) in enumerate(zip(event_ids, events_data)):
                activity = event_data.get("activity", "未命名活动")
                try:
                    # 构建单个事件的删除命令
                    commands = [
                        'tell application "Calendar"',
                        'activate',
                        'set calendarName to "TimeFlow"',
                        'set targetCalendar to calendar calendarName',
                        'tell targetCalendar',
                        f'set eventToDelete to event id "{event_id}"',
                        'delete eventToDelete',
                        'return "success"',
                        'end tell',
                        'end tell'
                    ]
                    
                    escaped_commands = [c.replace("'", "'\\''") for c in commands]
                    cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
                    
                    result = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        delete_results.append({
                            "event_id": event_id,
                            "activity": activity,
                            "success": True
                        })
                    else:
                        error_msg = result.stderr.strip() or result.stdout.strip() or "未知错误"
                        # 检查是否是事件不存在的错误（-1728）
                        if "-1728" in error_msg or "Can't get event" in error_msg or "对象不存在" in error_msg:
                            error_msg = "事件不存在（可能已被手动删除）"
                        delete_results.append({
                            "event_id": event_id,
                            "activity": activity,
                            "success": False,
                            "error": error_msg
                        })
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是事件不存在的错误
                    if "-1728" in error_msg or "Can't get event" in error_msg:
                        error_msg = "事件不存在（可能已被手动删除）"
                    delete_results.append({
                        "event_id": event_id,
                        "activity": activity,
                        "success": False,
                        "error": error_msg
                    })
            
            # 统计成功和失败的数量
            success_count = sum(1 for r in delete_results if r.get("success"))
            failed_count = len(delete_results) - success_count
            
            # 如果至少有一个成功，更新历史记录
            if success_count > 0:
                # 从历史记录中删除最近一次操作
                operations.pop(0)
                history["operations"] = operations
                
                with open(EVENT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                    json.dump(history, f, ensure_ascii=False, indent=2)
                
                # 更新最近事件文件（如果有下一个操作）
                if operations:
                    next_operation = operations[0]
                    with open(RECENT_EVENT_FILE, 'w', encoding='utf-8') as f:
                        json.dump({
                            "event_ids": next_operation.get("event_ids", []),
                            "events": next_operation.get("events", []),
                            "created_at": next_operation.get("created_at"),
                            "count": next_operation.get("count", 0)
                        }, f, ensure_ascii=False, indent=2)
                else:
                    # 没有更多操作，删除最近事件文件
                    if os.path.exists(RECENT_EVENT_FILE):
                        os.remove(RECENT_EVENT_FILE)
            
            # 即使所有事件都失败，也返回结果（而不是抛出异常）
            # 这样前端可以显示每个事件的详细状态
            return {
                "success": success_count > 0,  # 至少有一个成功才算整体成功
                "message": f"成功撤回 {success_count} 个事件，失败 {failed_count} 个",
                "deleted_count": success_count,
                "failed_count": failed_count,
                "results": delete_results,  # 每个事件的删除结果
                "deleted_events": events_data
            }
                
        except Exception as e:
            logger.error(f"从历史记录撤回失败: {e}")
            # Fallback 到旧的逻辑
    
    # Fallback：使用旧的最近事件文件（向后兼容）
    if not os.path.exists(RECENT_EVENT_FILE):
        return {"success": False, "error": "没有找到最近写入的事件"}
    
    try:
        with open(RECENT_EVENT_FILE, 'r', encoding='utf-8') as f:
            events_info = json.load(f)
        
        if "event_ids" in events_info:
            event_ids = events_info.get("event_ids", [])
            events_data = events_info.get("events", [])
        elif "event_id" in events_info:
            event_ids = [events_info.get("event_id")]
            events_data = [events_info]
        else:
            return {"success": False, "error": "事件ID不存在"}
        
        if not event_ids:
            return {"success": False, "error": "事件ID列表为空"}
        
        # 逐个删除事件，记录每个事件的删除状态（与主逻辑一致）
        delete_results = []
        for i, (event_id, event_data) in enumerate(zip(event_ids, events_data)):
            activity = event_data.get("activity", "未命名活动") if isinstance(event_data, dict) else "未命名活动"
            try:
                commands = [
                    'tell application "Calendar"',
                    'activate',
                    'set calendarName to "TimeFlow"',
                    'set targetCalendar to calendar calendarName',
                    'tell targetCalendar',
                    f'set eventToDelete to event id "{event_id}"',
                    'delete eventToDelete',
                    'return "success"',
                    'end tell',
                    'end tell'
                ]
                
                escaped_commands = [c.replace("'", "'\\''") for c in commands]
                cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    delete_results.append({
                        "event_id": event_id,
                        "activity": activity,
                        "success": True
                    })
                else:
                    error_msg = result.stderr.strip() or result.stdout.strip() or "未知错误"
                    # 检查是否是事件不存在的错误（-1728）
                    if "-1728" in error_msg or "Can't get event" in error_msg or "对象不存在" in error_msg:
                        error_msg = "事件不存在（可能已被手动删除）"
                    delete_results.append({
                        "event_id": event_id,
                        "activity": activity,
                        "success": False,
                        "error": error_msg
                    })
            except Exception as e:
                error_msg = str(e)
                # 检查是否是事件不存在的错误
                if "-1728" in error_msg or "Can't get event" in error_msg:
                    error_msg = "事件不存在（可能已被手动删除）"
                delete_results.append({
                    "event_id": event_id,
                    "activity": activity,
                    "success": False,
                    "error": error_msg
                })
        
        # 统计成功和失败的数量
        success_count = sum(1 for r in delete_results if r.get("success"))
        failed_count = len(delete_results) - success_count
        
        # 如果至少有一个成功，删除最近事件文件
        if success_count > 0:
            os.remove(RECENT_EVENT_FILE)
        
        # 即使所有事件都失败，也返回结果（而不是抛出异常）
        return {
            "success": success_count > 0,  # 至少有一个成功才算整体成功
            "message": f"成功撤回 {success_count} 个事件，失败 {failed_count} 个",
            "deleted_count": success_count,
            "failed_count": failed_count,
            "results": delete_results,
            "deleted_events": events_data if isinstance(events_data, list) else [events_data]
        }
            
    except FileNotFoundError:
        return {"success": False, "error": "没有找到最近写入的事件"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# API 路由
@app.get("/")
async def root():
    """返回前端页面"""
    # 使用 MacApp 的前端文件
    mac_app_static = os.path.join("MacApp", "static", "index.html")
    if os.path.exists(mac_app_static):
        return FileResponse(mac_app_static)
    else:
        raise FileNotFoundError("MacApp/static/index.html 不存在")


# 静态文件路由将在所有 API 路由注册后挂载（见文件末尾）
mac_app_static_dir = os.path.join("MacApp", "static")
if not os.path.exists(mac_app_static_dir):
    raise FileNotFoundError("MacApp/static 目录不存在")


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat completion endpoint
    """
    try:
        response = client.chat.completions.create(
            model=request.model,
            messages=request.messages
        )
        return {
            "choices": [{"message": {"content": response.choices[0].message.content}}]
        }
    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        return {"error": str(e)}


@app.post("/api/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("zh-CN"),
    use_local: Optional[bool] = Form(None)
):
    """
    转录音频文件为文本
    优先级：云端 API > Faster Whisper
    
    Args:
        audio_file: 音频文件
        language: 语言代码（如 zh-CN, en-US）
        use_local: 是否使用本地 STT 模型（None时默认使用云端API）
    
    Returns:
        转录文本和元数据
    """
    # 默认使用云端 API（准确率最高）
    use_local_stt = use_local if use_local is not None else USE_LOCAL_STT
    
    # 记录所有尝试的模型和错误
    stt_errors = []
    tried_models = []
    
    # 优先使用云端转录 API（准确率最高，推荐）
    if not use_local_stt:
        tried_models.append("云端 STT API")
        try:
            # 重置文件指针
            await audio_file.seek(0)
            
            # 准备文件上传
            files = {
                'audio_file': (audio_file.filename, await audio_file.read(), audio_file.content_type)
            }
            data = {
                'language': language
            }
            
            # 调用云端转录 API
            response = requests.post(
                TRANSCRIPTION_API_URL,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                transcript = result.get("text", "")
                logger.info(f"云端转录成功: {transcript[:50]}...")
                
                return {
                    "success": True,
                    "transcript": transcript,
                    "detected_language": result.get("detected_language"),
                    "confidence": result.get("confidence"),
                    "billing": result.get("billing"),
                    "method": "cloud"
                }
            else:
                raise Exception(f"云端转录 API 错误: {response.status_code} - {response.text}")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"云端转录失败: {error_msg}")
            # 检查是否是额度限制错误
            if "429" in error_msg or "limit" in error_msg.lower() or "quota" in error_msg.lower() or "SetLimitExceeded" in error_msg:
                error_detail = f"云端 STT API 已达到使用限制（429错误）"
            elif "401" in error_msg or "AuthenticationError" in error_msg:
                error_detail = f"云端 STT API 认证失败（401错误）"
            else:
                error_detail = f"云端 STT API 调用失败：{error_msg[:100]}"
            stt_errors.append(f"模型：云端 STT API - {error_detail}")
            # 回退到本地模型
            use_local_stt = True
    
    # 使用 Faster Whisper（备用本地模型）
    if use_local_stt and FASTER_WHISPER_AVAILABLE:
        tried_models.append(f"Faster Whisper ({WHISPER_MODEL_SIZE})")
        try:
            model = get_whisper_model()
            if model is None:
                raise Exception("Faster Whisper 模型未加载")
            
            # 保存上传的文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                content = await audio_file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                # 转录音频
                segments, info = model.transcribe(tmp_file_path, language=language.split('-')[0] if language else None)
                transcript = "".join([segment.text for segment in segments]).strip()
                transcript = normalize_transcript_text(transcript)
                
                return {
                    "success": True,
                    "transcript": transcript,
                    "detected_language": info.language,
                    "confidence": info.language_probability,
                    "method": "local",
                    "model": f"Faster-Whisper-{WHISPER_MODEL_SIZE}"
                }
            finally:
                # 清理临时文件
                os.unlink(tmp_file_path)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"本地转录失败: {e}")
            stt_errors.append(f"模型：Faster Whisper ({WHISPER_MODEL_SIZE}) - {error_msg[:100]}")
    
    # 如果所有方法都失败
    if not tried_models:
        tried_models.append("无可用模型（Faster Whisper 未安装）")
    
    return {
        "success": False,
        "error": "所有转录方法都失败",
        "step": "语音转文本",
        "tried_models": tried_models,
        "errors": stt_errors,
        "error_summary": f"语音转文本步骤失败：已尝试 {len(tried_models)} 个模型，全部失败。详情：{'；'.join(stt_errors)}"
    }


@app.post("/api/analyze")
async def analyze_time_entry(request: TimeAnalysisRequest):
    """
    使用 AI 分析转录文本，提取时间信息
    
    Args:
        request: 包含转录文本的请求
        use_ollama: 是否使用 Ollama（None 时使用环境变量配置）
    
    Returns:
        结构化时间数据
    """
    try:
        logger.info(f"分析时间记录: {request.transcript}")
        
        # 决定使用哪个 AI（优先级：Doubao > Supermind > Ollama）
        # 只有在 DOUBAO_API_KEY 存在时才使用豆包
        use_doubao = USE_DOUBAO and bool(DOUBAO_API_KEY)  # 默认使用豆包，但需要 API key
        use_local_ai = request.use_ollama if request.use_ollama is not None else USE_OLLAMA
        use_supermind = True  # Supermind 作为第二优先级
        
        # 记录所有尝试的模型和错误
        llm_errors = []
        tried_llm_models = []
        
        # 获取当前时间
        current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        current_time_iso = current_time.isoformat()
        
        # 计算相对时间的示例
        from datetime import timedelta
        current_dt = datetime.now()
        past_30min = current_dt - timedelta(minutes=30)
        past_30min_str = past_30min.strftime('%Y-%m-%dT%H:%M:%S')
        current_time_iso = current_dt.strftime('%Y-%m-%dT%H:%M:%S')
        
        # 从文件加载 Prompt 模板（如果存在）
        system_prompt = get_system_prompt(current_time_str)
        user_prompt = get_user_prompt(
            request.transcript,
            current_time_str,
            current_time_iso,
            current_dt,
            past_30min_str
        )

        # 记录使用的分析方法（优先级：Doubao > Supermind > Ollama）
        if use_doubao:
            analysis_method = "doubao"
            model_name = DOUBAO_MODEL
        elif use_supermind:
            analysis_method = "supermind"
            model_name = "supermind-agent-v1"
        elif use_local_ai:
            analysis_method = "ollama"
            model_name = OLLAMA_MODEL
        else:
            analysis_method = "supermind"  # 默认回退到 Supermind
            model_name = "supermind-agent-v1"
        
        if use_doubao:
            # 使用豆包云端模型（最佳性能：2.79秒，95.2%准确率）
            tried_llm_models.append(f"豆包 ({DOUBAO_MODEL})")
            try:
                logger.info(f"使用豆包模型: {DOUBAO_MODEL}")
                
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
                        "stream": False,
                        "temperature": 0.1,
                        "max_tokens": 1000
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    logger.info(f"豆包响应: {ai_response[:100]}...")
                else:
                    raise Exception(f"豆包 API 错误: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                error_msg = "连接失败"
                logger.warning("豆包 API 连接失败，回退到 Supermind")
                llm_errors.append(f"模型：豆包 ({DOUBAO_MODEL}) - 连接失败")
                use_doubao = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"豆包调用失败: {error_msg}，回退到 Supermind")
                # 检查是否是额度限制错误
                if "429" in error_msg or "SetLimitExceeded" in error_msg or "limit" in error_msg.lower():
                    error_detail = f"已达到使用限制（429错误）"
                elif "401" in error_msg or "AuthenticationError" in error_msg:
                    error_detail = f"认证失败（401错误）"
                else:
                    error_detail = f"调用失败：{error_msg[:100]}"
                llm_errors.append(f"模型：豆包 ({DOUBAO_MODEL}) - {error_detail}")
                use_doubao = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
        
        if not use_doubao and use_supermind:
            # 使用 Supermind 云端 API（第二优先级）
            tried_llm_models.append("Supermind (supermind-agent-v1)")
            try:
                logger.info("使用 Supermind 云端 API")
                response = client.chat.completions.create(
                    model="supermind-agent-v1",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                ai_response = response.choices[0].message.content.strip()
                logger.info(f"Supermind 响应: {ai_response[:100]}...")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Supermind 调用失败: {error_msg}，回退到本地 Ollama")
                # 检查是否是额度限制错误
                if "429" in error_msg or "limit" in error_msg.lower() or "quota" in error_msg.lower():
                    error_detail = f"已达到使用限制（429错误）"
                elif "401" in error_msg or "AuthenticationError" in error_msg:
                    error_detail = f"认证失败（401错误）"
                else:
                    error_detail = f"调用失败：{error_msg[:100]}"
                llm_errors.append(f"模型：Supermind (supermind-agent-v1) - {error_detail}")
                use_supermind = False
                analysis_method = "ollama" if use_local_ai else "supermind"
                model_name = OLLAMA_MODEL if use_local_ai else "supermind-agent-v1"
        
        if not use_doubao and not use_supermind and use_local_ai:
            # 使用 Ollama 本地模型（Chat API，更适合结构化输出）
            tried_llm_models.append(f"Ollama ({OLLAMA_MODEL})")
            try:
                logger.info(f"使用 Ollama 模型: {OLLAMA_MODEL}")
                
                response = requests.post(
                    f"{OLLAMA_API_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # 低温度，更确定性
                            "num_predict": 1000  # 支持多个时间块
                        }
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("message", {}).get("content", "").strip()
                    logger.info(f"Ollama 响应: {ai_response[:100]}...")
                else:
                    raise Exception(f"Ollama API 错误: {response.status_code} - {response.text}")
                    
            except requests.exceptions.ConnectionError:
                error_msg = "服务器未运行"
                logger.warning("Ollama 服务器未运行，回退到 Supermind")
                llm_errors.append(f"模型：Ollama ({OLLAMA_MODEL}) - 服务器未运行")
                use_local_ai = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Ollama 调用失败: {error_msg}，回退到 Supermind")
                llm_errors.append(f"模型：Ollama ({OLLAMA_MODEL}) - {error_msg[:100]}")
                use_local_ai = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
        
        # 如果所有方法都失败，使用 Supermind 作为最后回退
        if not use_doubao and not use_supermind and not use_local_ai:
            if "Supermind (supermind-agent-v1)" not in tried_llm_models:
                tried_llm_models.append("Supermind (supermind-agent-v1)")
            logger.info("所有方法都失败，使用 Supermind 作为最后回退")
            try:
                response = client.chat.completions.create(
                    model="supermind-agent-v1",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                ai_response = response.choices[0].message.content.strip()
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Supermind 也失败: {error_msg}")
                # 检查是否是额度限制错误
                if "429" in error_msg or "limit" in error_msg.lower() or "quota" in error_msg.lower():
                    error_detail = f"已达到使用限制（429错误）"
                elif "401" in error_msg or "AuthenticationError" in error_msg:
                    error_detail = f"认证失败（401错误）"
                else:
                    error_detail = f"调用失败：{error_msg[:100]}"
                llm_errors.append(f"模型：Supermind (supermind-agent-v1) - {error_detail}")
                
                # 构建详细的错误信息
                if not tried_llm_models:
                    tried_llm_models.append("无可用模型")
                
                error_summary = f"时间提取步骤失败：已尝试 {len(tried_llm_models)} 个模型，全部失败。详情：{'；'.join(llm_errors)}"
                raise Exception(error_summary)
        
        # 尝试提取 JSON（AI 可能返回带 markdown 代码块的 JSON）
        if "```json" in ai_response:
            ai_response = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            ai_response = ai_response.split("```")[1].split("```")[0].strip()
        
        # 解析 JSON（支持数组格式）
        try:
            time_data = json.loads(ai_response)
            # 如果返回的是数组，处理多个时间块
            if isinstance(time_data, list):
                if len(time_data) == 0:
                    # AI 返回了空数组，这是正常的（表示没有检测到时间信息），继续处理
                    logger.info("AI 返回了空数组（表示没有检测到时间信息）")
                    time_data = []  # 保持空数组，让后续验证逻辑处理
                else:
                    # 支持多个时间块，返回数组格式
                    logger.info(f"AI 返回了 {len(time_data)} 个时间块")
                    logger.info(f"所有时间块: {json.dumps(time_data, ensure_ascii=False, indent=2)}")
                    # 保持数组格式，前端会处理多个事件
            elif isinstance(time_data, dict):
                # 如果是单个对象，转换为数组格式（统一格式）
                time_data = [time_data]
            else:
                raise ValueError(f"AI 返回了意外的数据类型: {type(time_data)}")
            
            # 后处理：修正相对时间的计算（处理数组中的每个时间块）
            transcript_lower = request.transcript.lower()
            relative_time_keywords = ["刚刚", "刚才", "刚刚半小时", "刚刚半小時", "半小时前", "半小時前"]
            has_relative_time = any(keyword in transcript_lower for keyword in relative_time_keywords)
            
            # 确保 time_data 是数组格式
            if not isinstance(time_data, list):
                time_data = [time_data] if isinstance(time_data, dict) else []
            
            # 处理每个时间块，验证并过滤无效的时间块
            processed_time_data = []
            for time_block in time_data:
                if not isinstance(time_block, dict):
                    continue
                
                # 验证时间块的有效性
                start_time_str = time_block.get('start_time', '')
                end_time_str = time_block.get('end_time', '')
                activity = time_block.get('activity', '').strip()
                
                # 如果缺少开始时间或结束时间，跳过
                if not start_time_str or not end_time_str:
                    logger.warning(f"时间块缺少开始时间或结束时间，跳过: {activity}")
                    continue
                
                # 如果活动名称为空或无效（如"无"、"没有"），跳过
                if not activity or activity.lower() in ['无', '没有', 'none', 'null', '']:
                    logger.warning(f"时间块活动名称为空或无效，跳过: {activity}")
                    continue
                
                try:
                    # 解析时间
                    if 'Z' in start_time_str:
                        start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    else:
                        start_dt = datetime.fromisoformat(start_time_str)
                    
                    if 'Z' in end_time_str:
                        end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    else:
                        end_dt = datetime.fromisoformat(end_time_str)
                    
                    # 移除时区信息
                    if start_dt.tzinfo:
                        start_dt = start_dt.replace(tzinfo=None)
                    if end_dt.tzinfo:
                        end_dt = end_dt.replace(tzinfo=None)
                    
                    # 验证时间段有效性
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    
                    # 如果开始时间 >= 结束时间，或持续时间少于1分钟，跳过
                    if duration_seconds <= 60:  # 少于1分钟视为无效
                        logger.warning(f"时间块持续时间过短（{duration_seconds}秒），跳过: {activity} ({start_time_str} - {end_time_str})")
                        continue
                    
                    # 时间块有效，继续处理
                except Exception as e:
                    logger.warning(f"时间块时间解析失败，跳过: {activity}, 错误: {e}")
                    continue
                    
                # 在描述字段末尾添加模型名称
                current_description = time_block.get('description', '') or ''
                current_description = current_description.strip().rstrip('-').strip()
                if current_description:
                    time_block['description'] = f"{current_description} [模型: {model_name}]"
                else:
                    time_block['description'] = f"[模型: {model_name}]"
                
                # 处理标签（tag）字段
                # 如果 AI 没有返回 tag，或 tag 为空/无效，根据关键词自动分类
                tags_config = load_tags_config()
                valid_tag_names = [tag.get("name") for tag in tags_config.get("tags", [])]
                
                current_tag = time_block.get('tag', '').strip()
                
                if not current_tag or current_tag == '未分类' or current_tag not in valid_tag_names:
                    # 自动分类
                    tag = classify_activity_tag(
                        time_block.get('activity', ''),
                        current_description
                    )
                    time_block['tag'] = tag
                    logger.info(f"自动分类标签: {time_block.get('activity')} -> {tag}")
                else:
                    # AI 返回了有效的 tag，使用它
                    logger.info(f"使用AI返回的标签: {time_block.get('activity')} -> {current_tag}")
                
                # 修正相对时间
                if has_relative_time:
                    logger.info(f"检测到相对时间关键词，进行后处理修正")
                    # 检查结束时间是否接近当前时间（允许5分钟误差）
                    if time_block.get('end_time'):
                        try:
                            end_time_str = time_block['end_time']
                            # 处理时区信息
                            if 'Z' in end_time_str:
                                end_dt = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                            elif '+' in end_time_str or end_time_str.count('-') > 2:
                                end_dt = datetime.fromisoformat(end_time_str)
                            else:
                                end_dt = datetime.fromisoformat(end_time_str)
                            
                            # 移除时区信息
                            if end_dt.tzinfo:
                                end_dt = end_dt.replace(tzinfo=None)
                            
                            now_dt = datetime.now()
                            time_diff = abs((end_dt - now_dt).total_seconds())
                            
                            logger.info(f"结束时间: {end_dt}, 当前时间: {now_dt}, 时间差: {time_diff}秒")
                            
                            # 如果结束时间与当前时间相差超过5分钟，修正为当前时间
                            if time_diff > 300:  # 5分钟 = 300秒
                                logger.info(f"修正结束时间：{time_block['end_time']} -> {current_time_iso}")
                                time_block['end_time'] = current_time_iso
                            else:
                                # 即使时间差小于5分钟，也要确保结束时间是当前时间（相对时间的特性）
                                logger.info(f"结束时间接近当前时间，但仍需确保是当前时间")
                                time_block['end_time'] = current_time_iso
                            
                            # 如果开始时间也需要修正（"刚刚半小时"）
                            if "半小时" in transcript_lower or "半小時" in transcript_lower:
                                start_dt = current_dt - timedelta(minutes=30)
                                corrected_start = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
                                # 检查开始时间是否需要修正
                                if time_block.get('start_time'):
                                    try:
                                        start_time_str = time_block['start_time']
                                        if 'Z' in start_time_str:
                                            start_dt_parsed = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                                        elif '+' in start_time_str or start_time_str.count('-') > 2:
                                            start_dt_parsed = datetime.fromisoformat(start_time_str)
                                        else:
                                            start_dt_parsed = datetime.fromisoformat(start_time_str)
                                        
                                        if start_dt_parsed.tzinfo:
                                            start_dt_parsed = start_dt_parsed.replace(tzinfo=None)
                                        
                                        start_diff = abs((start_dt_parsed - start_dt).total_seconds())
                                        if start_diff > 300:  # 如果开始时间与期望值相差超过5分钟
                                            logger.info(f"修正开始时间：{time_block.get('start_time')} -> {corrected_start}")
                                            time_block['start_time'] = corrected_start
                                    except Exception as e:
                                        logger.warning(f"检查开始时间时出错: {e}")
                                else:
                                    time_block['start_time'] = corrected_start
                                    logger.info(f"设置开始时间：{corrected_start}")
                            else:
                                logger.info(f"结束时间接近当前时间，无需修正")
                        except Exception as e:
                            logger.warning(f"修正相对时间时出错: {e}")
                            import traceback
                            traceback.print_exc()
                
                processed_time_data.append(time_block)
            
            # 如果处理后没有有效的时间块，返回空数组
            if not processed_time_data:
                logger.warning("处理后没有有效的时间块（可能因为时间点无效、时间段过短、或活动名称为空）")
                return {
                    "success": True,
                    "data": [],
                    "raw_response": ai_response,
                    "method": analysis_method,
                    "model": model_name,
                    "message": "未检测到有效的时间段（需要完整的开始时间和结束时间，且持续时间至少1分钟）"
                }
            
            time_data = processed_time_data
        except json.JSONDecodeError:
            logger.warning(f"AI 返回的不是有效 JSON，尝试修复: {ai_response}")
            # 尝试提取 JSON（支持数组和对象）
            import re
            # 先尝试提取数组
            array_match = re.search(r'\[.*?\]', ai_response, re.DOTALL)
            if array_match:
                try:
                    time_data = json.loads(array_match.group())
                    if not isinstance(time_data, list):
                        time_data = [time_data]
                except:
                    pass
            # 如果数组提取失败，尝试提取对象
            if not isinstance(time_data, list):
                json_match = re.search(r'\{.*?\}', ai_response, re.DOTALL)
                if json_match:
                    try:
                        time_data = json.loads(json_match.group())
                        time_data = [time_data] if isinstance(time_data, dict) else []
                    except:
                        raise ValueError("无法解析 AI 响应为 JSON")
                else:
                    raise ValueError("无法解析 AI 响应为 JSON")
        
        # 确保 time_data 是数组格式
        if isinstance(time_data, dict):
            time_data = [time_data]
        elif not isinstance(time_data, list):
            time_data = []
        
        logger.info(f"AI 分析结果: {len(time_data)} 个时间块")
        logger.info(f"使用方法: {analysis_method}")
        
        return {
            "success": True,
            "data": time_data,  # 返回数组格式，支持多个时间块
            "raw_response": ai_response,
            "method": analysis_method,
            "model": model_name
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"分析异常: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # 检查错误信息中是否包含模型信息
        tried_models = tried_llm_models if 'tried_llm_models' in locals() else []
        errors = llm_errors if 'llm_errors' in locals() else []
        
        return {
            "success": False,
            "error": error_msg,
            "step": "时间提取",
            "tried_models": tried_models if tried_models else ["未知"],
            "errors": errors if errors else [error_msg],
            "error_summary": error_msg if error_msg.startswith("时间提取步骤失败") else f"时间提取步骤失败：{error_msg}"
        }


@app.post("/api/mobile/process")
async def mobile_process(
    request: Request,
    audio_file: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    recording: Optional[UploadFile] = File(None),
):
    """
    移动端聚合接口：接收音频 -> 转写 -> 分析 -> 返回结构化 events
    供 iOS 快捷指令使用。

    兼容多种字段名（包括 iOS Shortcuts 可能出现的中文字段名），以及直接发送 audio/* 的情况。
    """
    try:
        logger.info("收到移动端处理请求 /api/mobile/process")
        content_type = request.headers.get("content-type", "")
        logger.info(f"Content-Type: {content_type}")

        audio_file_obj: Optional[UploadFile] = None

        # 1) FastAPI 参数注入（最稳定）
        for candidate, name in (
            (audio_file, "audio_file"),
            (file, "file"),
            (audio, "audio"),
            (recording, "recording"),
        ):
            if candidate is not None:
                audio_file_obj = candidate
                logger.info(f"找到音频文件字段: {name}")
                break

        # 2) iOS 可能会直接以 audio/* 发送原始 body
        if audio_file_obj is None and content_type.startswith("audio/"):
            body = await request.body()
            if not body:
                raise HTTPException(status_code=400, detail="请求体为空，未收到音频数据")

            audio_ext = ".wav"
            if "mpeg" in content_type or "mp3" in content_type:
                audio_ext = ".mp3"
            elif "mp4" in content_type or "m4a" in content_type:
                audio_ext = ".m4a"

            from io import BytesIO

            audio_file_obj = UploadFile(
                file=BytesIO(body),
                filename=f"recording{audio_ext}",
                headers={"content-type": content_type},
            )
            logger.info(f"从 raw body 读取音频成功，大小: {len(body)} bytes")

        # 3) 手动解析 multipart（兼容中文字段名）
        if audio_file_obj is None:
            try:
                form = await request.form()
                keys = list(form.keys())
                logger.info(f"表单字段: {keys}")

                possible_field_names = [
                    "audio_file",
                    "录制的音频",
                    "音频",
                    "file",
                    "audio",
                    "recording",
                ]
                for field_name in possible_field_names:
                    if field_name in form and isinstance(form[field_name], UploadFile):
                        audio_file_obj = form[field_name]
                        logger.info(f"找到音频文件字段(表单): {field_name}")
                        break

                if audio_file_obj is None:
                    # 兜底：取第一个 UploadFile
                    for k in keys:
                        v = form.get(k)
                        if isinstance(v, UploadFile):
                            audio_file_obj = v
                            logger.info(f"使用第一个文件字段(表单): {k}")
                            break
            except Exception as e:
                # 典型：Missing boundary in multipart
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"无法解析表单数据: {e}. "
                        "请在 iOS 快捷指令的“获取 URL 内容”里选择“请求体=文件”，"
                        "并且不要手动设置 Content-Type（让系统自动带 boundary）。"
                    ),
                )

        if audio_file_obj is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "未找到音频文件。请确保 iOS 快捷指令的“获取 URL 内容”使用 POST，"
                    "请求体选择“文件”，并选中“录制的音频/文件”。"
                ),
            )

        # 1) 转写
        transcript_result = await transcribe_audio(audio_file=audio_file_obj, language="zh-CN", use_local=None)
        if not transcript_result.get("success"):
            # 返回详细的错误信息
            error_info = {
                "success": False,
                "step": transcript_result.get("step", "语音转文本"),
                "error": transcript_result.get("error", "未知错误"),
                "error_summary": transcript_result.get("error_summary", transcript_result.get("error", "转写失败")),
                "tried_models": transcript_result.get("tried_models", []),
                "errors": transcript_result.get("errors", [])
            }
            return error_info

        transcript = transcript_result.get("transcript", "")
        transcript = normalize_transcript_text(transcript)

        # 2) 分析
        analysis_request = TimeAnalysisRequest(transcript=transcript)
        analysis_result = await analyze_time_entry(analysis_request)
        if not analysis_result.get("success"):
            # 返回详细的错误信息
            error_info = {
                "success": False,
                "step": analysis_result.get("step", "时间提取"),
                "error": analysis_result.get("error", "未知错误"),
                "error_summary": analysis_result.get("error_summary", analysis_result.get("error", "分析失败")),
                "tried_models": analysis_result.get("tried_models", []),
                "errors": analysis_result.get("errors", []),
                "transcript": transcript  # 即使分析失败，也返回转录文本
            }
            return error_info

        return {
            "success": True,
            "transcript": transcript,
            "events": analysis_result.get("data", []),
            "stt_method": transcript_result.get("method", "unknown"),  # 记录使用的 STT 方法
            "llm_method": analysis_result.get("method", "unknown"),  # 记录使用的 LLM 方法
            "llm_model": analysis_result.get("model", "unknown")  # 记录使用的 LLM 模型
        }

    except HTTPException as e:
        logger.error(f"移动端处理失败: {e.detail}")
        return {"success": False, "error": e.detail}
    except Exception as e:
        logger.error(f"移动端处理失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


@app.post("/api/calendar/add")
async def add_to_calendar_api(request: CalendarEventRequest):
    """
    添加到苹果日历（单个事件）
    
    Args:
        request: 日历事件数据
    
    Returns:
        添加结果（包含事件ID）
    """
    try:
        # 如果请求中没有指定 calendar_name，尝试从事件数据中获取 tag
        calendar_name = request.calendar_name
        if not calendar_name:
            # 可以从事件数据中提取 tag（如果前端传递了）
            # 这里暂时使用请求中的 calendar_name，如果没有则使用默认值
            calendar_name = "TimeFlow"
        
        # 从请求中获取 tag，如果没有则从 calendar_name 推断
        tag = getattr(request, 'tag', None) or calendar_name
        
        # 根据 tag 获取标签颜色
        tag_info = get_tag_by_name(tag)
        tag_color = tag_info.get("color", "#95E1D3")
        
        event_data = {
            "activity": request.activity,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "description": request.description or "",
            "location": request.location or "",
            "calendar_name": calendar_name,  # 支持指定日历（标签）
            "tag": tag,  # 保存 tag 字段用于前端显示
            "tag_color": tag_color,  # 标签颜色（用于设置日历颜色）
            "recurrence": request.recurrence  # 支持重复规则
        }
        
        result = add_to_calendar_via_applescript(event_data)
        
        if result.get("success"):
            # 同时写入备忘录：追加到指定备忘录（默认“时间”）
            try:
                note_name = request.note_name or "时间"
                note_text = format_note_entry(event_data)
                notes_result = append_to_notes_via_applescript(note_name, note_text)
                if not notes_result.get("success"):
                    logger.warning(f"写入备忘录失败: {notes_result.get('error')}")
            except Exception as e:
                logger.warning(f"写入备忘录异常: {e}")

            return {
                "success": True,
                "event_id": result.get("event_id"),
                "message": result.get("message", "事件已添加到日历")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "未知错误")
            }
            
    except Exception as e:
        logger.error(f"添加到日历异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/calendar/add-multiple")
async def add_multiple_to_calendar_api(events: List[CalendarEventRequest]):
    """
    批量添加到苹果日历（多个事件）
    
    Args:
        events: 日历事件数据列表
    
    Returns:
        添加结果（包含所有事件ID）
    """
    try:
        event_ids = []
        events_data = []
        errors = []
        
        for event_request in events:
            # 如果请求中没有指定 calendar_name，使用默认值
            calendar_name = event_request.calendar_name or "TimeFlow"
            
            # 从请求中获取 tag，如果没有则从 calendar_name 推断
            tag = getattr(event_request, 'tag', None) or calendar_name
            
            event_data = {
                "activity": event_request.activity,
                "start_time": event_request.start_time,
                "end_time": event_request.end_time,
                "description": event_request.description or "",
                "location": event_request.location or "",
                "calendar_name": calendar_name,  # 支持指定日历（标签）
                "tag": tag,  # 保存 tag 字段用于前端显示
                "recurrence": event_request.recurrence  # 支持重复规则
            }
            
            result = add_to_calendar_via_applescript(event_data)
            
            if result.get("success"):
                event_id = result.get("event_id")
                event_ids.append(event_id)
                events_data.append(event_data)
            else:
                errors.append({
                    "event": event_data,
                    "error": result.get("error", "未知错误")
                })
        
        if event_ids:
            # 保存所有事件信息（用于撤回）
            save_recent_events(event_ids, events_data)

            # 同时写入备忘录：把本次事件按两行格式追加（一次性追加，避免多次 AppleScript）
            try:
                note_name = (events[0].note_name if events and getattr(events[0], "note_name", None) else None) or "时间"
                blocks = [format_note_entry(e) for e in events_data if isinstance(e, dict)]
                note_text = "\n\n".join([b for b in blocks if b.strip()])
                if note_text.strip():
                    notes_result = append_to_notes_via_applescript(note_name, note_text)
                    if not notes_result.get("success"):
                        logger.warning(f"批量写入备忘录失败: {notes_result.get('error')}")
            except Exception as e:
                logger.warning(f"批量写入备忘录异常: {e}")
            
            return {
                "success": True,
                "event_ids": event_ids,
                "count": len(event_ids),
                "message": f"成功添加 {len(event_ids)} 个事件到日历",
                "errors": errors if errors else None
            }
        else:
            return {
                "success": False,
                "error": "所有事件添加失败",
                "errors": errors
            }
            
    except Exception as e:
        logger.error(f"批量添加到日历异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/calendar/recent")
async def get_recent_events():
    """
    获取最近一次写入的日历事件（用于前端显示）
    
    Returns:
        最近一次操作的所有事件
    """
    try:
        # 优先从历史记录读取
        if os.path.exists(EVENT_HISTORY_FILE):
            with open(EVENT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            operations = history.get("operations", [])
            if operations:
                last_operation = operations[0]
                events = last_operation.get("events", [])
                # 确保每个事件都有 tag 字段（从 calendar_name 推断）
                for event in events:
                    if "tag" not in event or not event.get("tag"):
                        event["tag"] = event.get("calendar_name", "生活")
                return {
                    "success": True,
                    "events": events,
                    "count": last_operation.get("count", 0),
                    "created_at": last_operation.get("created_at")
                }
        
        # Fallback：从最近事件文件读取
        if os.path.exists(RECENT_EVENT_FILE):
            with open(RECENT_EVENT_FILE, 'r', encoding='utf-8') as f:
                events_info = json.load(f)
            
            events = events_info.get("events", [])
            # 确保每个事件都有 tag 字段（从 calendar_name 推断）
            for event in events:
                if "tag" not in event or not event.get("tag"):
                    event["tag"] = event.get("calendar_name", "生活")
            if "event_id" in events_info:
                # 旧格式兼容
                events = [events_info]
            
            return {
                "success": True,
                "events": events,
                "count": len(events),
                "created_at": events_info.get("created_at")
            }
        
        return {
            "success": True,
            "events": [],
            "count": 0
        }
        
    except Exception as e:
        logger.error(f"获取最近事件异常: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "events": [],
            "count": 0
        }


@app.post("/api/calendar/undo")
async def undo_last_calendar_events():
    """
    撤回最近写入的日历事件（一次操作的所有事件）
    
    Returns:
        撤回结果（包含撤回的事件数量）
    """
    try:
        result = undo_last_events_via_applescript()
        return result
    except Exception as e:
        logger.error(f"撤回事件异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/time-entry")
async def save_time_entry(entry: TimeEntry):
    """
    保存时间记录条目
    
    Args:
        entry: 时间记录条目
    
    Returns:
        保存结果
    """
    try:
        # 读取现有日志
        if os.path.exists(TIME_LOG_FILE):
            with open(TIME_LOG_FILE, 'r', encoding='utf-8') as f:
                time_log = json.load(f)
        else:
            time_log = {"entries": []}
        
        # 添加新条目
        entry_dict = entry.dict()
        time_log["entries"].append(entry_dict)
        
        # 保存到文件
        with open(TIME_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(time_log, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存时间记录: {entry.activity}")
        
        return {
            "success": True,
            "message": "时间记录已保存"
        }
        
    except Exception as e:
        logger.error(f"保存时间记录异常: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/calendar/tags")
async def get_calendar_tags():
    """
    获取用户日历中的标签和分类
    返回：日历名称、常用关键词、活动分类等
    """
    try:
        # 获取所有日历名称
        calendars_script = '''
        tell application "Calendar"
            set calendarNames to {}
            repeat with cal in calendars
                set end of calendarNames to name of cal
            end repeat
            return calendarNames
        end tell
        '''
        
        calendars_result = subprocess.run(
            ["osascript", "-e", calendars_script],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        calendars = []
        if calendars_result.returncode == 0:
            calendars = [name.strip() for name in calendars_result.stdout.strip().split(',') if name.strip()]
        
        # 获取最近事件摘要（限制数量避免超时）
        summaries_script = '''
        tell application "Calendar"
            set eventSummaries to {}
            set startDate to (current date) - 30 * days
            set endDate to (current date) + 1 * days
            set eventCount to 0
            
            repeat with i from 1 to (count of calendars)
                if i > 5 or eventCount >= 50 then exit repeat
                try
                    set cal to calendar i
                    set eventsList to (every event of cal whose start date is greater than startDate and start date is less than endDate)
                    repeat with evt in eventsList
                        if eventCount >= 50 then exit repeat
                        if summary of evt is not "" then
                            set end of eventSummaries to summary of evt
                            set eventCount to eventCount + 1
                        end if
                    end repeat
                end try
            end repeat
            
            return eventSummaries
        end tell
        '''
        
        summaries_result = subprocess.run(
            ["osascript", "-e", summaries_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        summaries = []
        if summaries_result.returncode == 0:
            summaries = [s.strip() for s in summaries_result.stdout.strip().split(',') if s.strip()]
        
        # 提取关键词
        keywords = []
        if summaries:
            all_words = []
            for summary in summaries:
                cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', summary)
                words = cleaned.split()
                all_words.extend(words)
            
            word_freq = Counter(all_words)
            filtered_words = {
                word: count for word, count in word_freq.items()
                if len(word) >= 2 and len(word) <= 10 and count >= 2
            }
            keywords = [word for word, count in sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)[:20]]
        
        # 提取分类
        categories = set()
        activity_keywords = {
            '工作': ['会议', '工作', '项目', '讨论', '汇报', 'ddl', 'submit', 'report'],
            '学习': ['学习', '课程', '读书', '作业', '复习', 'test', 'exam'],
            '运动': ['运动', '跑步', '健身', '游泳', '瑜伽', '跳舞', '遛'],
            '娱乐': ['电影', '游戏', '音乐', '唱歌', '练歌'],
            '社交': ['聚餐', '吃饭', '咖啡', '见面', '聚会'],
            '生活': ['购物', '买菜', '做饭', '家务', '休息'],
            '出行': ['出门', '通勤', '旅行', '出差', '回家'],
        }
        
        for summary in summaries:
            summary_lower = summary.lower()
            for category, keywords_list in activity_keywords.items():
                if any(keyword in summary_lower for keyword in keywords_list):
                    categories.add(category)
        
        return {
            "success": True,
            "data": {
                "calendars": calendars,
                "keywords": keywords,
                "categories": list(categories),
                "recent_summaries": summaries[:10]  # 最近10个摘要作为参考
            }
        }
        
    except Exception as e:
        logger.error(f"获取日历标签失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {
                "calendars": [],
                "keywords": [],
                "categories": [],
                "recent_summaries": []
            }
        }


@app.get("/api/tags")
async def get_tags():
    """
    获取所有标签配置
    
    Returns:
        标签列表
    """
    try:
        tags_config = load_tags_config()
        return {
            "success": True,
            "tags": tags_config.get("tags", [])
        }
    except Exception as e:
        logger.error(f"获取标签失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "tags": []
        }


@app.post("/api/tags")
async def create_tag(tag: dict):
    """
    创建新标签
    
    Args:
        tag: 标签数据 {name, description, color}
    
    Returns:
        创建结果
    """
    try:
        tags_config = load_tags_config()
        tags = tags_config.get("tags", [])
        
        # 生成新ID
        new_id = tag.get("id") or f"tag_{len(tags) + 1}"
        
        # 检查名称是否重复
        if any(t.get("name") == tag.get("name") for t in tags):
            return {
                "success": False,
                "error": f"标签名称 '{tag.get('name')}' 已存在"
            }
        
        new_tag = {
            "id": new_id,
            "name": tag.get("name", ""),
            "description": tag.get("description", ""),
            "color": tag.get("color", "#95E1D3"),
            "is_default": False
        }
        
        tags.append(new_tag)
        tags_config["tags"] = tags
        
        with open(TAGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tags_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"创建标签: {new_tag['name']}")
        return {
            "success": True,
            "tag": new_tag
        }
    except Exception as e:
        logger.error(f"创建标签失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.put("/api/tags/{tag_id}")
async def update_tag(tag_id: str, tag: dict):
    """
    更新标签
    
    Args:
        tag_id: 标签ID
        tag: 更新的标签数据
    
    Returns:
        更新结果
    """
    try:
        tags_config = load_tags_config()
        tags = tags_config.get("tags", [])
        
        # 找到要更新的标签
        tag_index = None
        for i, t in enumerate(tags):
            if t.get("id") == tag_id:
                tag_index = i
                break
        
        if tag_index is None:
            return {
                "success": False,
                "error": f"标签 ID '{tag_id}' 不存在"
            }
        
        # 允许修改所有标签（包括默认标签）
        old_tag = tags[tag_index]
        
        # 检查名称是否与其他标签重复
        if tag.get("name") and tag.get("name") != old_tag.get("name"):
            if any(t.get("name") == tag.get("name") for t in tags if t.get("id") != tag_id):
                return {
                    "success": False,
                    "error": f"标签名称 '{tag.get('name')}' 已存在"
                }
        
        # 更新标签
        tags[tag_index].update({
            "name": tag.get("name", old_tag.get("name")),
            "description": tag.get("description", old_tag.get("description")),
            "color": tag.get("color", old_tag.get("color"))
        })
        
        tags_config["tags"] = tags
        
        with open(TAGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tags_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"更新标签: {tag_id}")
        
        # 如果更新了颜色，同步更新苹果日历中对应日历的颜色
        updated_tag = tags[tag_index]
        if tag.get("color") and tag.get("color") != old_tag.get("color"):
            try:
                calendar_name = updated_tag.get("name")
                tag_color = tag.get("color")
                r, g, b = hex_to_rgb(tag_color)
                
                # 使用 AppleScript 更新日历颜色
                commands = [
                    'tell application "Calendar"',
                    'activate',
                    f'set calendarName to "{escape_apple_script(calendar_name)}"',
                    'try',
                    f'set targetCalendar to calendar calendarName',
                    f'set color of targetCalendar to {{{r}, {g}, {b}}}',
                    'end try',
                    'end tell'
                ]
                
                escaped_commands = [c.replace("'", "'\\''") for c in commands]
                cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
                
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info(f"已同步更新日历颜色: {calendar_name} -> {tag_color}")
                else:
                    logger.warning(f"同步日历颜色失败: {result.stderr.strip()}")
            except Exception as e:
                logger.warning(f"同步日历颜色异常: {e}")
        
        return {
            "success": True,
            "tag": tags[tag_index]
        }
    except Exception as e:
        logger.error(f"更新标签失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: str):
    """
    删除标签（默认标签不允许删除）
    
    Args:
        tag_id: 标签ID
    
    Returns:
        删除结果
    """
    try:
        tags_config = load_tags_config()
        tags = tags_config.get("tags", [])
        
        # 找到要删除的标签
        tag_index = None
        for i, t in enumerate(tags):
            if t.get("id") == tag_id:
                tag_index = i
                break
        
        if tag_index is None:
            return {
                "success": False,
                "error": f"标签 ID '{tag_id}' 不存在"
            }
        
        # 允许删除所有标签（包括默认标签）
        # 注意：删除默认标签后，用户需要手动重新创建
        
        deleted_tag = tags.pop(tag_index)
        tags_config["tags"] = tags
        
        with open(TAGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tags_config, f, ensure_ascii=False, indent=2)
        
        logger.info(f"删除标签: {deleted_tag.get('name')}")
        return {
            "success": True,
            "message": f"已删除标签: {deleted_tag.get('name')}"
        }
    except Exception as e:
        logger.error(f"删除标签失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/time-entries")
async def get_time_entries(date: Optional[str] = None):
    """
    获取时间记录列表
    
    Args:
        date: 可选，过滤日期（YYYY-MM-DD格式）
    
    Returns:
        时间记录列表
    """
    try:
        if not os.path.exists(TIME_LOG_FILE):
            return {
                "success": True,
                "entries": []
            }
        
        with open(TIME_LOG_FILE, 'r', encoding='utf-8') as f:
            time_log = json.load(f)
        
        entries = time_log.get("entries", [])
        
        # 如果指定了日期，过滤记录
        if date:
            filtered_entries = [
                entry for entry in entries
                if entry.get("start_time", "").startswith(date) or
                   entry.get("end_time", "").startswith(date)
            ]
            return {
                "success": True,
                "entries": filtered_entries
            }
        
        return {
            "success": True,
            "entries": entries
        }
        
    except Exception as e:
        logger.error(f"获取时间记录异常: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


# 在所有 API 路由注册后，挂载静态文件（避免覆盖 API 路由）
# 注意：静态文件路由必须放在最后，否则会覆盖 /api/* 路由
if os.path.exists(mac_app_static_dir):
    app.mount("/static", StaticFiles(directory=mac_app_static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
