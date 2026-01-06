#!/usr/bin/env python3
"""
TimeFlow MVP - 语音时间记录应用
FastAPI 后端服务
"""
from fastapi import FastAPI, File, UploadFile, Form
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

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FunASR (优先使用，中文识别最准确)
try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except ImportError:
    FUNASR_AVAILABLE = False
    logger.warning("FunASR 未安装，中文转录功能不可用。安装: pip install funasr modelscope torchaudio")

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
RECENT_EVENT_FILE = "data/recent_event.json"  # 存储最近写入的事件信息

# 确保数据目录存在
os.makedirs("data", exist_ok=True)

# FunASR 模型（懒加载，默认使用）
funasr_model = None
FUNASR_MODEL_NAME = os.getenv("FUNASR_MODEL", "paraformer-zh")  # FunASR 中文模型（正确格式：paraformer-zh）
USE_FUNASR = os.getenv("USE_FUNASR", "true").lower() == "true"  # 默认使用 FunASR

# Faster Whisper 模型（懒加载，备用）
whisper_model = None
# 根据基准测试，tiny 是最快的模型（0.3秒），推荐用于实时场景
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "tiny")  # tiny, base, small, medium, large
USE_LOCAL_STT = os.getenv("USE_LOCAL_STT", "false").lower() == "true"  # 如果FunASR不可用，使用Whisper

# Ollama 配置
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
# 根据基准测试，llama3.2:latest 是最快的本地模型（3秒），多时间块提取准确
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"

# 豆包云端模型配置（根据基准测试，doubao-1-5-lite-32k-250115 是最佳模型：2.79秒，95.2%准确率）
DOUBAO_API_URL = os.getenv("DOUBAO_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "490b8b89-b9ed-44af-8a8b-f70d660ee797")
DOUBAO_MODEL = os.getenv("DOUBAO_MODEL", "doubao-1-5-lite-32k-250115")
USE_DOUBAO = os.getenv("USE_DOUBAO", "true").lower() == "true"  # 默认使用豆包模型


def get_funasr_model():
    """懒加载 FunASR 模型"""
    global funasr_model
    if funasr_model is None and FUNASR_AVAILABLE:
        try:
            logger.info(f"加载 FunASR 模型: {FUNASR_MODEL_NAME}")
            funasr_model = AutoModel(model=FUNASR_MODEL_NAME, model_revision="v2.0.4")
            logger.info("✅ FunASR 模型加载成功")
        except Exception as e:
            logger.error(f"❌ FunASR 模型加载失败: {e}")
            funasr_model = None
    return funasr_model

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
    """获取格式化后的 System Prompt"""
    template, _ = load_prompts_from_file()
    
    if template is None:
        # 使用默认 prompt（向后兼容）
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
    
    # 替换模板变量
    return template.format(current_time_str=current_time_str)


def get_user_prompt(transcript: str, current_time_str: str, current_time_iso: str, 
                     current_dt: datetime, past_30min_str: str) -> str:
    """获取格式化后的 User Prompt"""
    _, template = load_prompts_from_file()
    
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
  - 结果：[{{"activity": "通勤/去咖啡厅", "start_time": "{current_dt.strftime('%Y-%m-%d')}T08:00:00", "end_time": "{current_dt.strftime('%Y-%m-%d')}T09:00:00", "location": "咖啡厅"}},
         {{"activity": "学习", "start_time": "{current_dt.strftime('%Y-%m-%d')}T09:00:00", "end_time": "{current_dt.strftime('%Y-%m-%d')}T09:30:00", "location": "咖啡厅"}}]

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
    return template.format(
        transcript=transcript,
        current_time_str=current_time_str,
        current_time_iso=current_time_iso,
        current_dt=current_dt,
        past_30min_str=past_30min_str
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


# 工具函数
def escape_apple_script(text):
    """转义 AppleScript 特殊字符"""
    if not text:
        return ''
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def save_recent_events(event_ids: List[str], events_data: List[dict]):
    """保存最近写入的多个事件信息（一次操作可能写入多个事件）"""
    events_info = {
        "event_ids": event_ids,  # 多个事件ID
        "events": events_data,  # 多个事件的完整数据
        "created_at": datetime.now().isoformat(),
        "count": len(event_ids)
    }
    try:
        with open(RECENT_EVENT_FILE, 'w', encoding='utf-8') as f:
            json.dump(events_info, f, ensure_ascii=False, indent=2)
        logger.info(f"已保存最近 {len(event_ids)} 个事件信息")
    except Exception as e:
        logger.warning(f"保存最近事件信息失败: {e}")


def add_to_calendar_via_applescript(event_data: dict) -> dict:
    """使用 AppleScript 添加到苹果日历，返回事件ID"""
    activity = event_data.get('activity', '未命名活动')
    start_time = event_data.get('start_time')
    end_time = event_data.get('end_time')
    description = event_data.get('description', '') or event_data.get('location', '')
    
    # 转义特殊字符
    escaped_activity = escape_apple_script(activity)
    escaped_description = escape_apple_script(description)
    
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
        'set calendarName to "TimeFlow"',
        'try',
        'set targetCalendar to calendar calendarName',
        'on error',
        'make new calendar with properties {name:calendarName}',
        'set targetCalendar to calendar calendarName',
        'end try',
        'tell targetCalendar',
        f'make new event at end with properties {{summary:"{escaped_activity}", start date:(current date) + {start_seconds}, end date:(current date) + {end_seconds}, description:"{escaped_description}"}}',
        'set newEvent to result',
        'set eventId to id of newEvent',
        'return eventId',
        'end tell',
        'end tell'
    ]
    
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
    """撤回最近写入的多个日历事件（一次操作的所有事件）"""
    # 读取最近的事件信息
    if not os.path.exists(RECENT_EVENT_FILE):
        return {"success": False, "error": "没有找到最近写入的事件"}
    
    try:
        with open(RECENT_EVENT_FILE, 'r', encoding='utf-8') as f:
            events_info = json.load(f)
        
        # 支持新旧格式兼容
        if "event_ids" in events_info:
            # 新格式：多个事件
            event_ids = events_info.get("event_ids", [])
            events_data = events_info.get("events", [])
        elif "event_id" in events_info:
            # 旧格式：单个事件（兼容）
            event_ids = [events_info.get("event_id")]
            events_data = [events_info]
        else:
            return {"success": False, "error": "事件ID不存在"}
        
        if not event_ids:
            return {"success": False, "error": "事件ID列表为空"}
        
        # 构建 AppleScript 命令（删除多个事件）
        commands = [
            'tell application "Calendar"',
            'activate',
            'set calendarName to "TimeFlow"',
            'set targetCalendar to calendar calendarName',
            'tell targetCalendar'
        ]
        
        # 为每个事件ID添加删除命令
        for event_id in event_ids:
            commands.append(f'set eventToDelete to event id "{event_id}"')
            commands.append('delete eventToDelete')
        
        commands.extend([
            'return "success"',
            'end tell',
            'end tell'
        ])
        
        # 转义单引号
        escaped_commands = [c.replace("'", "'\\''") for c in commands]
        
        # 使用多个 -e 参数执行 AppleScript
        cmd = "osascript " + " ".join([f"-e '{c}'" for c in escaped_commands])
        
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # 多个事件可能需要更长时间
        )
        
        if result.returncode == 0:
            # 删除事件信息文件
            os.remove(RECENT_EVENT_FILE)
            return {
                "success": True,
                "message": f"已撤回 {len(event_ids)} 个事件",
                "deleted_count": len(event_ids),
                "deleted_events": events_data
            }
        else:
            return {"success": False, "error": result.stderr.strip()}
            
    except FileNotFoundError:
        return {"success": False, "error": "没有找到最近写入的事件"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# API 路由
@app.get("/")
async def root():
    """返回前端页面"""
    # 使用 CalendarApp 的前端文件
    calendar_app_static = os.path.join("CalendarApp", "static", "index.html")
    if os.path.exists(calendar_app_static):
        return FileResponse(calendar_app_static)
    else:
        raise FileNotFoundError("CalendarApp/static/index.html 不存在")


# 挂载静态文件（使用 CalendarApp 的静态文件）
calendar_app_static_dir = os.path.join("CalendarApp", "static")
if os.path.exists(calendar_app_static_dir):
    app.mount("/static", StaticFiles(directory=calendar_app_static_dir), name="static")
else:
    raise FileNotFoundError("CalendarApp/static 目录不存在")


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
    优先级：FunASR > Faster Whisper > 云端API
    
    Args:
        audio_file: 音频文件
        language: 语言代码（如 zh-CN, en-US）
        use_local: 是否使用本地 STT 模型（None时默认使用FunASR）
    
    Returns:
        转录文本和元数据
    """
    # 默认使用本地模型（FunASR优先）
    use_local_stt = use_local if use_local is not None else (USE_FUNASR or USE_LOCAL_STT)
    
    # 优先使用 FunASR（中文识别最准确）
    if use_local_stt and USE_FUNASR and FUNASR_AVAILABLE:
        try:
            model = get_funasr_model()
            if model is None:
                raise Exception("FunASR 模型未加载")
            
            # 保存上传的文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                content = await audio_file.read()
                tmp_file.write(content)
                tmp_file_path = tmp_file.name
            
            try:
                # 转录音频
                res = model.generate(input=tmp_file_path)
                transcript = res[0]["text"] if res and len(res) > 0 else ""
                
                logger.info(f"FunASR 转录成功: {transcript[:50]}...")
                
                return {
                    "success": True,
                    "transcript": transcript,
                    "detected_language": language.split('-')[0] if language else "zh",
                    "confidence": 1.0,  # FunASR 不提供置信度
                    "method": "local",
                    "model": f"FunASR-{FUNASR_MODEL_NAME}"
                }
            finally:
                # 清理临时文件
                os.unlink(tmp_file_path)
                
        except Exception as e:
            logger.error(f"FunASR 转录失败: {e}")
            # 回退到其他模型
            use_local_stt = True  # 继续尝试其他本地模型
    
    # 使用 Faster Whisper（备用本地模型）
    if use_local_stt and FASTER_WHISPER_AVAILABLE:
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
                transcript = " ".join([segment.text for segment in segments])
                
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
            logger.error(f"本地转录失败: {e}")
            # 回退到云端转录
            use_local_stt = False
    
    # 使用云端转录 API（最后备选）
    if not use_local_stt:
        # 使用云端转录 API
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
            logger.error(f"云端转录失败: {e}")
            return {
                "success": False,
                "error": str(e)
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
        use_doubao = USE_DOUBAO  # 默认使用豆包
        use_local_ai = request.use_ollama if request.use_ollama is not None else USE_OLLAMA
        use_supermind = True  # Supermind 作为第二优先级
        
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
                logger.warning("豆包 API 连接失败，回退到 Supermind")
                use_doubao = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
            except Exception as e:
                logger.error(f"豆包调用失败: {str(e)}，回退到 Supermind")
                use_doubao = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
        
        if not use_doubao and use_supermind:
            # 使用 Supermind 云端 API（第二优先级）
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
                logger.error(f"Supermind 调用失败: {str(e)}，回退到本地 Ollama")
                use_supermind = False
                analysis_method = "ollama" if use_local_ai else "supermind"
                model_name = OLLAMA_MODEL if use_local_ai else "supermind-agent-v1"
        
        if not use_doubao and not use_supermind and use_local_ai:
            # 使用 Ollama 本地模型（Chat API，更适合结构化输出）
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
                logger.warning("Ollama 服务器未运行，回退到 Supermind")
                use_local_ai = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
            except Exception as e:
                logger.error(f"Ollama 调用失败: {str(e)}，回退到 Supermind")
                use_local_ai = False
                analysis_method = "supermind"
                model_name = "supermind-agent-v1"
        
        # 如果所有方法都失败，使用 Supermind 作为最后回退
        if not use_doubao and not use_supermind and not use_local_ai:
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
                logger.error(f"Supermind 也失败: {str(e)}")
                raise Exception("所有 AI 服务都不可用")
        
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
                    raise ValueError("AI 返回了空数组")
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
            
            # 处理每个时间块
            processed_time_data = []
            for time_block in time_data:
                if not isinstance(time_block, dict):
                    continue
                    
                # 在描述字段末尾添加模型名称
                current_description = time_block.get('description', '') or ''
                current_description = current_description.strip().rstrip('-').strip()
                if current_description:
                    time_block['description'] = f"{current_description} [模型: {model_name}]"
                else:
                    time_block['description'] = f"[模型: {model_name}]"
                
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
        logger.error(f"分析异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


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
        event_data = {
            "activity": request.activity,
            "start_time": request.start_time,
            "end_time": request.end_time,
            "description": request.description or "",
            "location": request.location or ""
        }
        
        result = add_to_calendar_via_applescript(event_data)
        
        if result.get("success"):
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
            event_data = {
                "activity": event_request.activity,
                "start_time": event_request.start_time,
                "end_time": event_request.end_time,
                "description": event_request.description or "",
                "location": event_request.location or ""
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
