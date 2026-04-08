# 随便：菜谱智能推荐agent

**"随便" Agent —— 你的专属美食推荐小助手，让选择困难症成为历史！**

每天都在纠结"今天吃什么"？别慌，随便 Agent 来拯救你。它记得你的口味，懂你的偏好，还能从本地菜谱库和网络帮你找到最适合今天的那道菜。

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

## Implementation

### 环境安装

```bash
pip install -r requirements.txt
```

### 环境变量配置

创建 `.env` 文件：

```env
AGENT_MODEL_ID=your_model_id
AGENT_API_KEY=your_api_key
AGENT_BASE_URL=your_base_url
```

### 运行

```bash
cd src
python whatever_agent.py
```

### 目录结构

```
whatever-to-eat/
├── src/
│   ├── whatever_agent.py      # Agent 主入口
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
