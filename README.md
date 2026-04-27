# 随便：菜谱智能推荐agent

🤖：今天吃什么？
😴：随便……
🤖：不要随便了！我来给你推荐今天吃什么！

## 核心功能

### 智能菜谱推荐
- **本地向量库搜索**：基于你已经收藏的菜谱，语义理解你的需求（"想吃清淡的鸡肉" → 自动匹配相关菜谱）
- **网络搜索补充**：当本地库没有满意答案时，自动搜索网络获取更多选择
- **灵活过滤**：支持按难度、食材、口味等多维度筛选

### 长期记忆
- 记住你喜欢的口味、不喜欢的食物、忌口过敏源
- 追踪你近期的饮食历史，避免天天吃同样的菜
- 每次对话后，Agent 会根据你的反馈智能更新记忆

### 营养搭配
- 推荐不仅考虑口味，还注重荤素搭配和营养均衡
- 根据你的厨艺水平推荐合适难度的菜谱

## API 接口

启动 API 服务后可通过以下接口调用：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/register` | POST | 注册新用户 |
| `/chat` | POST | 流式对话（返回 SSE） |
| `/chat_sync` | POST | 同步对话 |
| `/history/{user_id}` | GET | 获取对话历史 |

## Implementation

### 环境安装

```bash
pip install -r requirements.txt
```

### 环境变量配置

创建 `.env` 文件：

```env
# agent 相关配置
AGENT_API_KEY=your-api-key
AGENT_MODEL_ID=your-model
AGENT_BASE_URL=your-url

# embedding 相关配置
EMBEDDING_API_KEY=your-api-key-for-embedding
EMBEDDING_MODEL_ID="text-embedding-3-large"
EMBEDDING_BASE_URL=embedding-url
```

### 运行

> **重要**：所有命令需在项目根目录（`whatever-to-eat/`）下执行，不要进入 `src/` 目录。

#### 命令行模式

```bash
cd whatever-to-eat
python src/whatever_agent.py
```

#### API 服务模式

```bash
cd whatever-to-eat
uvicorn src.api:app --reload --port 8000
```

### Docker 部署

确保已安装 Docker Desktop，然后在项目根目录执行：

```bash
# 构建并启动（首次运行需加 --build）
docker compose up --build

# 后台运行
docker compose up -d

# 查看日志
docker compose logs -f

# 停止容器
docker compose down
```

启动后：
- **API 服务** → http://localhost:8000
- **Gradio Web 界面** → http://localhost:7860

`.env` 配置文件会自动挂载到容器中。修改代码后重新构建需加 `--build`。

#### Gradio Web 界面

```bash
cd whatever-to-eat
python src/web_demo.py
```

访问 http://localhost:7860

### 目录结构

```
whatever-to-eat/
├── src/
│   ├── whatever_agent.py      # Agent 主入口（CLI）
│   ├── api.py                 # FastAPI 后端服务
│   ├── web_demo.py            # Gradio 前端界面
│   ├── user_memory.py        # 用户记忆管理
│   ├── prompt_template.py    # 系统提示词模板
│   ├── recipe_retrieval_tool.py  # 本地向量库搜索
│   └── web_search_tool.py    # 网络搜索
├── users_history/             # 用户记忆存储目录
└── data/                     # 菜谱向量库数据
```

## 评估

### 本地知识库检索

### web检索

### agent回复
