# 功能测试

本文件夹包含所有功能测试脚本，用于验证功能是否正常工作。

## 📁 测试脚本列表

### Ollama 相关测试
- `test_ollama.py` - Ollama 基础功能测试
- `test_ollama_integration.py` - Ollama 集成测试
- `quick_test_ollama.py` - Ollama 快速测试

### STT 相关测试
- `test_faster_whisper.py` - Faster Whisper 测试
- `test_elevenlabs_scribe.py` - ElevenLabs Scribe 测试

### 功能测试
- `test_hotkey_recording.py` - 快捷键录音测试

## 🚀 运行测试

```bash
# 运行单个测试
python3 test_ollama.py

# 运行所有测试
for test in test_*.py; do
    echo "Running $test..."
    python3 "$test"
done
```

## 📝 测试文档

测试相关文档位于：`../docs/tests/`

