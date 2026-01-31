# API Keys 安全管理指南

## ⚠️ 重要安全原则

**绝对不要将 API keys、private keys 或任何敏感信息提交到公开的 GitHub 仓库！**

## 为什么不能提交 API keys？

1. **公开仓库任何人都能看到**：一旦提交，所有历史记录都会包含这些密钥
2. **GitHub 会扫描并警告**：GitHub 会自动检测并警告泄露的密钥
3. **恶意使用**：他人可能使用你的 API keys，导致：
   - 费用损失
   - 服务滥用
   - 账户被封禁
   - 数据泄露

## 当前代码中的安全问题

### ❌ 发现的问题

在 `app.py` 第 206 行有一个硬编码的默认 API key：

```python
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY", "490b8b89-b9ed-44af-8a8b-f70d660ee797")
```

**这个默认值不应该存在**，应该强制从环境变量读取。

## 正确的做法

### 1. 使用环境变量（推荐）

**代码中**：
```python
# ✅ 正确：强制从环境变量读取，没有默认值
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
if not DOUBAO_API_KEY:
    raise ValueError("DOUBAO_API_KEY 环境变量未设置")
```

**本地开发**：
创建 `.env` 文件（已在 `.gitignore` 中）：
```bash
DOUBAO_API_KEY=your_real_key_here
SUPER_MIND_API_KEY=your_real_key_here
AI_BUILDER_TOKEN=your_real_key_here
```

**云端部署**：
通过部署平台的环境变量配置传递，**不提交到代码仓库**。

### 2. 创建 .env.example 模板

创建一个 `.env.example` 文件（**可以提交到 Git**），作为模板：

```bash
# API Keys（不要提交真实值到 Git）
DOUBAO_API_KEY=your_doubao_api_key_here
SUPER_MIND_API_KEY=your_supermind_api_key_here
AI_BUILDER_TOKEN=your_ai_builder_token_here

# 可选配置
USE_LOCAL_STT=false
WHISPER_MODEL_SIZE=tiny
USE_DOUBAO=true
```

### 3. 确保 .gitignore 正确配置

检查 `.gitignore` 是否包含：
```
.env
*.env
.env.local
.env.*.local
```

## AI Builder Space 部署时的安全做法

### 方式 1：通过部署 API 传递环境变量（推荐）

部署时通过 `env_vars` 字段传递：

```json
{
  "repo_url": "https://github.com/lindapu-1/TimeFlow",
  "service_name": "timeflow",
  "branch": "main",
  "port": 8000,
  "env_vars": {
    "DOUBAO_API_KEY": "your_real_key",
    "SUPER_MIND_API_KEY": "your_real_key"
  }
}
```

**注意**：
- ✅ 这些值**不会**存储在平台数据库中
- ✅ 只传递给 Koyeb 容器
- ✅ **不会**出现在代码仓库中
- ✅ 每次部署都需要重新提供

### 方式 2：使用部署配置文件（本地保存）

创建 `deploy-config.json`（**不要提交到 Git**）：

```json
{
  "repo_url": "https://github.com/lindapu-1/TimeFlow",
  "service_name": "timeflow",
  "branch": "main",
  "port": 8000,
  "env_vars": {
    "DOUBAO_API_KEY": "your_real_key",
    "SUPER_MIND_API_KEY": "your_real_key"
  }
}
```

在 `.gitignore` 中添加：
```
deploy-config.json
*.config.json
```

## 如果已经泄露了 API keys 怎么办？

### 立即行动：

1. **撤销泄露的 API keys**
   - 登录相关服务提供商
   - 立即撤销/删除泄露的密钥
   - 生成新的 API keys

2. **从 Git 历史中移除**（如果可能）
   ```bash
   # 警告：这会重写 Git 历史，需要强制推送
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch app.py" \
     --prune-empty --tag-name-filter cat -- --all
   ```
   
   **或者**：联系 GitHub 支持，请求删除敏感信息

3. **检查使用情况**
   - 查看 API 使用日志
   - 检查是否有异常调用
   - 监控费用变化

## 最佳实践总结

### ✅ 应该做的：

1. ✅ 使用环境变量存储 API keys
2. ✅ 创建 `.env.example` 作为模板
3. ✅ 确保 `.env` 在 `.gitignore` 中
4. ✅ 代码中强制检查环境变量是否存在
5. ✅ 部署时通过平台环境变量传递
6. ✅ 定期轮换 API keys

### ❌ 不应该做的：

1. ❌ 硬编码 API keys 在代码中
2. ❌ 提交 `.env` 文件到 Git
3. ❌ 在代码注释中包含真实 API keys
4. ❌ 在公开的 Issue 或 PR 中提及 API keys
5. ❌ 使用默认值作为真实的 API keys

## 检查清单

部署前检查：

- [ ] `.env` 文件在 `.gitignore` 中
- [ ] 代码中没有硬编码的 API keys
- [ ] 创建了 `.env.example` 模板
- [ ] 所有 API keys 都从环境变量读取
- [ ] 代码中检查环境变量是否存在
- [ ] 部署配置不包含在代码仓库中

## 参考资源

- [GitHub 安全最佳实践](https://docs.github.com/en/code-security/secret-scanning)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
- [12 Factor App - Config](https://12factor.net/config)
