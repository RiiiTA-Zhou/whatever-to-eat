import json
import os
from datetime import datetime
from typing import Optional, List, Dict
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import SystemMessage

load_dotenv()

# =========== 用户记忆管理器 ===========
class UserMemoryManager:
    """管理用户的持久化记忆"""
    
    def __init__(self, user_id: str, storage_dir: str = "./users_history"):
        self.user_id = user_id
        self.storage_dir = storage_dir
        self.memory_path = os.path.join(storage_dir, f"{user_id}.json")
        
        # 确保目录存在
        os.makedirs(storage_dir, exist_ok=True)
        
        # 加载记忆
        self.memory = self._load()
    
    def _load(self) -> dict:
        """从文件加载用户记忆"""
        if os.path.exists(self.memory_path):
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 初始化默认记忆结构
        os.makedirs(self.memory_path, exist_ok=True)
        memory_temlpate = {
            "user_id": self.user_id,
            "preferences": {
                "tastes": [],
                "dislikes": [],
                "avoid": [],
                "difficulty_preference": None
            },
            "recent_meals": []
        }
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(memory_temlpate, f, ensure_ascii=False, indent=4)
        return memory_temlpate
    
    def _save(self):
        """保存用户记忆到文件"""
        with open(self.memory_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
    
    def get_system_context(self):
        """生成用于 SystemMessage 的上下文文本"""
        prefs = self.memory["preferences"]
        recent = self.memory["recent_meals"]
        
        preference_text = []
        
        # 口味偏好
        if prefs.get("tastes"):
            preference_text.append(f"用户喜欢这些口味：{', '.join(prefs['tastes'])}")
        if prefs.get("dislikes"):
            preference_text.append(f"用户不喜欢：{', '.join(prefs['dislikes'])}")
        if prefs.get("avoid"):
            preference_text.append(f"用户忌口：{', '.join(prefs['avoid'])}")
        if prefs.get("difficulty_preference"):
            preference_text.append(f"用户偏好难度：{prefs['difficulty_preference']}（1小白都会→5超级大厨）")
        
        preference_text = "\n".join(preference_text)
        
        # 近期饮食（最近7天）
        if recent:
            recent_text = [f"{m['date']}: {m['dish']}" for m in recent[:7]]
            recent_text = "\n".join(recent_text)
        
        return preference_text, recent_text
    
    def update_from_conversation(self, conversation_text: str, llm):
        """从对话中提取并更新用户偏好（可选，调用 LLM 提取）"""
        
        prompt = f"""从以下对话中提取用户的饮食偏好变化，只输出 JSON。

对话：
{conversation_text}

现有偏好：
{json.dumps(self.memory["preferences"], ensure_ascii=False, indent=2)}

请输出更新后的偏好：
{{
    "tastes": ["现在的口味"],
    "dislikes": ["现在的不喜欢"],
    "avoid": ["现在的忌口"],
    "difficulty_preference": 数字或null
}}

只输出 JSON，不要其他内容。更新后的偏好应该是现有偏好的基础上进行增量更新或者对现有偏好的纠正。"""
        
        try:
            response = llm.invoke(prompt)
            new_prefs = json.loads(response.content)
            
            # 合并新偏好
            self.memory["preferences"] = new_prefs
            
            self._save()
        except Exception as e:
            print(f"更新偏好失败: {e}")
    
    def add_recent_meal(self, dish_name: str):
        """添加近期饮食记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 检查今天是否已记录
        recent = self.memory["recent_meals"]
        if recent and recent[0]["date"] == today:
            # 今天已有记录，合并
            existing = recent[0]["dish"]
            if dish_name not in existing:
                recent[0]["dish"] = f"{existing}，{dish_name}"
        else:
            # 新增记录
            recent.insert(0, {
                "date": today,
                "dish": dish_name
            })
        
        # 只保留最近30条记录
        self.memory["recent_meals"] = recent[:30]
        self._save()
    
    def add_preference(self, key: str, value):
        """手动添加偏好"""
        if key in self.memory["preferences"]:
            if isinstance(self.memory["preferences"][key], list):
                if value not in self.memory["preferences"][key]:
                    self.memory["preferences"][key].append(value)
            else:
                self.memory["preferences"][key] = value
            self._save()


# =========== 定义工具 ===========
@tool
def search_recipes(query: str) -> str:
    """执行基础菜谱搜索。
    
    Args:
        query: 搜索关键词，如'麻辣香锅'、'宫保鸡丁'
    """
    # 这里是你的实际检索逻辑
    return f"找到关于'{query}'的菜谱：麻辣香锅、麻婆豆腐"

@tool
def search_recipes_with_filters(query: str, difficulty: int = None, ingredients: list = None) -> str:
    """执行菜谱搜索，支持按难度和食材过滤。
    
    Args:
        query: 搜索关键词
        difficulty: 难度级别，1简单，2中等，3困难
        ingredients: 必须包含的食材列表
    """
    return f"找到符合条件（难度{difficulty}，食材{ingredients}）的菜谱：宫保鸡丁"

@tool
def web_search(query: str) -> str:
    """从网络搜索菜谱，仅当本地找不到时使用。
    
    Args:
        query: 要搜索的菜名
    """
    return f"网络搜索到'{query}'的做法：..."

# =========== 创建带记忆的 Agent ===========
class RecipeAgent:
    def __init__(self, user_id: str, vector_store=None):
        self.user_id = user_id
        self.vector_store = vector_store
        self.memory_manager = UserMemoryManager(user_id)
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base=os.getenv("DEEPSEEK_BASE_URL"),
            temperature=0.3
        )
        
        # 会话记忆（用于多轮对话）
        self.conversation_memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )
        
        # 记录本次对话的推荐菜品（用于结束时更新记忆）
        self.recommended_dishes = []
        
        # 创建 Agent
        self.agent_executor = self._create_agent()
    
    def _create_agent(self):
        """创建带用户画像的 Agent"""
        
        # 获取用户画像上下文
        user_context = self.memory_manager.get_system_context()
        
        # 构建完整的系统提示词
        system_prompt = f"""你是一个专业的菜谱推荐助手。

{user_context}

你可以使用以下工具：
- search_recipes: 基础菜谱搜索
- search_recipes_with_filters: 带过滤条件的搜索
- web_search: 网络搜索（仅当本地找不到时使用）

使用规则：
1. 推荐菜品时必须考虑用户的口味偏好和忌口
2. 避免推荐用户最近吃过的菜品
3. 如果用户表达了新的偏好（如"我不吃XX"、"我喜欢XX"），记住并在后续推荐中应用

回答要清晰、友好，推荐菜品时说明理由。"""
        
        # 定义工具列表
        tools = [search_recipes, search_recipes_with_filters, web_search]
        
        # ReAct 提示词模板
        react_prompt = PromptTemplate.from_template("""
{system_prompt}

工具：{tools}
工具名称：{tool_names}

使用以下格式：
Question: 用户的问题
Thought: 思考要做什么
Action: 工具名称
Action Input: 工具的输入（JSON格式）
Observation: 工具返回的结果
... (重复)
Thought: 我知道答案了
Final Answer: 给用户的最终回答

开始！

Question: {input}
Thought: {agent_scratchpad}
""")
        
        # 创建 Agent
        agent = create_react_agent(
            llm=self.llm,
            tools=tools,
            prompt=react_prompt.partial(system_prompt=