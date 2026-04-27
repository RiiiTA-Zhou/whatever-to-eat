# Agent 架构图

```mermaid
graph TB
    %% 样式定义
    classDef input fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    classDef core fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef tool fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef rag fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef web fill:#e0f7fa,stroke:#00838f,stroke-width:2px
    classDef memory fill:#fce4ec,stroke:#c2185b,stroke-width:2px
    classDef storage fill:#efebe9,stroke:#5d4037,stroke-width:2px,stroke-dasharray: 5 5

    %% ===== 用户输入层 =====
    CLI["💻 命令行 CLI<br/>whatever_agent.py"]
    API["🌐 FastAPI 接口<br/>api.py"]
    WebUI["🎨 Gradio 前端<br/>web_demo.py"]

    %% ===== Agent 核心 =====
    subgraph AgentCore ["Agent 核心 (LangChain ReAct)"]
        direction TB
        LLM["🧠 大语言模型<br/>DeepSeek Chat"]
        SP["📋 系统提示词<br/>prompt_template.py"]
        LC["⚙️ LangGraph Agent<br/>create_agent() + checkpointer"]
    end

    %% ===== 工具层 =====
    RAG["🔍 RAG 搜索工具<br/>search_recipes()<br/>search_recipes_with_filters()"]
    WebSearch["🌐 网络搜索工具<br/>web_search()"]
    MemUpdate["📝 记忆更新工具<br/>update_memory_as_tool()"]

    %% ===== RAG 子系统 =====
    subgraph RAGSubsystem ["RAG 检索增强生成"]
        direction TB
        Embedding["📊 OpenAI Embedding<br/>text-embedding-3-large"]
        Chroma["💾 Chroma 向量数据库<br/>recipe_db/"]
        Filter["🔎 元数据过滤<br/>难度/菜名/食材"]
        RawData["📄 源数据<br/>data/recipes.json"]
    end

    %% ===== 网络搜索子系统 =====
    subgraph WebSubsystem ["网络搜索模块"]
        direction TB
        DDG["🦆 DuckDuckGo 搜索<br/>ddgs 库"]
        Fetch["📥 网页内容抓取<br/>trafilatura / BeautifulSoup"]
    end

    %% ===== 用户偏好记忆子系统 =====
    subgraph MemSubsystem ["用户偏好记忆模块"]
        direction TB
        UMM["👤 UserMemoryManager<br/>user_memory.py"]
        Prefs["❤️ 偏好信息<br/>口味 / 忌口 / 难度"]
        History["📅 饮食历史<br/>最近用餐记录"]
        Store["💾 持久化存储<br/>users_history/{user_id}.json"]
    end

    %% ===== 连接 =====
    CLI --> LC
    API --> LC
    WebUI --> LC
    LLM --> LC
    SP --> LC

    LC --> RAG
    LC --> WebSearch
    LC --> MemUpdate

    RAG --> Embedding
    Embedding --> Chroma
    Chroma --> RawData
    Chroma --> Filter

    WebSearch --> DDG
    DDG --> Fetch

    MemUpdate --> UMM
    UMM --> Prefs
    UMM --> History
    Prefs --> Store
    History --> Store

    Store -.->|"读取用户上下文"| SP

    %% 点击交互
    click CLI "https://github.com/RiiiTA-Zhou/whatever-to-eat/blob/main/src/whatever_agent.py"
    click API "https://github.com/RiiiTA-Zhou/whatever-to-eat/blob/main/src/api.py"
    click WebUI "https://github.com/RiiiTA-Zhou/whatever-to-eat/blob/main/src/web_demo.py"

    %% 应用样式
    class CLI,API,WebUI input
    class LLM,SP,LC core
    class RAG,WebSearch,MemUpdate tool
    class Embedding,Chroma,Filter,RawData rag
    class DDG,Fetch web
    class UMM,Prefs,History,Store memory
```

## 数据流说明

### 1. RAG 搜索流程
```
用户查询 → 语义搜索 → Embedding 向量化 → Chroma 相似度检索
  → 元数据过滤（难度/菜名/食材） → 返回匹配菜谱
```

### 2. 网络搜索流程
```
用户查询 → DuckDuckGo 搜索 → 网页内容提取（trafilatura/BS4）
  → 清洗格式化 → 返回搜索摘要
```

### 3. 用户偏好记忆流程
```
对话中提取偏好 → update_memory_as_tool() 工具调用
  → UserMemoryManager 更新内存 → 写入 users_history/*.json
  → 刷新系统提示词 → 后续对话感知用户偏好
```
