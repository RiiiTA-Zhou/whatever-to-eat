import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from recipe_retrieval_tool import load_vector_store, dense_search, search_with_filters
from web_search_tool import ddg_search
from user_memory import UserMemoryManager
from prompt_template import system_prompt_builder
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.tools import StructuredTool

load_dotenv()

# =========== 定义工具 ===========

vector_store = load_vector_store()

@tool
def search_recipes_with_filters(query: str, difficulty: int | None = None, ingredients: list[str] | None = None) -> str:
    """从本地数据库搜索菜谱，支持难度和食材过滤
    
    Args:
        query: 搜索关键词，如'清淡的鸡肉菜'，或'辣椒炒肉'
        difficulty: 菜谱难度级别，1-5，1表示新手小白都会，3是较为复杂的家常菜，5是需要厨师水平的菜
        ingredients: 关键食材列表，如['鸡肉', '辣椒']"""
    try:
        results = search_with_filters(
            vector_store,
            query=query,
            k=3,
            difficulty_level=difficulty,
            key_ingredients=ingredients
        )
        
        return results
    except Exception as e:
        return f"搜索失败: {str(e)}"

@tool   
def search_recipes(query: str) -> str:
    """从本地数据库搜索菜谱
    
    Args:
        query: 搜索关键词，如'清淡的鸡肉菜'，或'辣椒炒肉'"""
    try:
        results = dense_search(vector_store, query=query, k=3)
        return results
    except Exception as e:
        return f"搜索失败: {str(e)}"

@tool
def web_search(query: str) -> str:
    """执行外部网络搜索

    Args:
        query: 搜索关键词，如'猪肺汤'，或'香辣 螃蟹'"""
    try:
        return ddg_search(query)
    except Exception as e:
        return f"网络搜索失败: {str(e)}"

# =========== 定义 Agent ===========

tools = [search_recipes_with_filters, search_recipes, web_search]

llm = ChatOpenAI(
    model = os.getenv("AGENT_MODEL_ID"),
    api_key = os.getenv("AGENT_API_KEY"),
    base_url = os.getenv("AGENT_BASE_URL"),
    temperature = 0.8,
    timeout = 40,
    streaming=True,
)



class RecipeAgent:
    def __init__(self, user_id: str, llm, tools):
        self.user_id = user_id
        self.llm = llm
        self.tools = tools

        self.user_memory = UserMemoryManager(user_id)

        # 用于保持同一用户的对话记忆（跨轮次）
        self.conversation_history = []

        # 持久化 checkpointer，整个会话生命周期复用
        self.checkpointer = InMemorySaver()

        # 创建 update_memory_as_tool（直接更新记忆，不调 LLM）
        self.update_memory_tool = StructuredTool.from_function(
            func=self._update_memory_impl,
            name="update_memory_as_tool",
            description="""直接更新用户长期偏好记忆。当用户在对话中明确表达了饮食偏好变化时调用。

        Args:
            tastes: 用户喜欢的新口味列表，会替换现有口味（如 ["清淡", "鲜香"]）
            dislikes: 用户不喜欢的事物列表（如 ["太油腻的", "内脏"]）
            avoid: 用户忌口/过敏的食物列表（如 ["牛奶", "海鲜"]）
            difficulty_preference: 菜谱难度偏好 1-5，1=新手小白，3=家常复杂，5=专业大厨
            add_recent_meal: 用户确认要吃的菜品列表（如 ["宫保鸡丁", "番茄炒蛋"]），会记录到近期饮食历史
            update_reason: 更新原因简述，如"用户说最近想吃清淡的，不喜欢辣的了"

        【何时调用】
        - 用户明确说想尝试新口味/菜系时
        - 用户说不想吃某种食物了/不喜欢某口味了时
        - 用户提到过敏或忌口时
        - 用户确认了今天/这顿要吃的具体菜品时
        - 用户表达了新的难度偏好时，如想做更简单方便的菜、想挑战难度更高的菜
        注意：如果用户只是问问题、闲聊，不需要调用此工具。"""
        )

        self._refresh_system_prompt()

        self.config = {"configurable": {"thread_id": user_id}}

        self.agent = create_agent(
            model=self.llm,
            tools=self.tools + [self.update_memory_tool],
            system_prompt=self.system_prompt,
            checkpointer=self.checkpointer
        )

    def _update_memory_impl(
        self,
        tastes: list[str] | None = None,
        dislikes: list[str] | None = None,
        avoid: list[str] | None = None,
        difficulty_preference: int | None = None,
        add_recent_meal: list[str] | None = None,
        update_reason: str = ""
    ) -> str:
        """直接更新记忆的实现"""
        updated = []

        if tastes is not None:
            self.user_memory.memory["preferences"]["tastes"] = tastes
            updated.append(f"口味偏好更新为: {tastes}")
        if dislikes is not None:
            self.user_memory.memory["preferences"]["dislikes"] = dislikes
            updated.append(f"不喜欢更新为: {dislikes}")
        if avoid is not None:
            self.user_memory.memory["preferences"]["avoid"] = avoid
            updated.append(f"忌口更新为: {avoid}")
        if difficulty_preference is not None:
            self.user_memory.memory["preferences"]["difficulty_preference"] = difficulty_preference
            updated.append(f"难度偏好更新为: {difficulty_preference}")

        if updated:
            self.user_memory._save()
            msg = f"已更新用户偏好。更新原因：{update_reason}。更新内容：{'；'.join(updated)}"
        elif add_recent_meal:
            self.user_memory.add_recent_meal(add_recent_meal)
            msg = f"已记录近期饮食：{', '.join(add_recent_meal)}"
        else:
            msg = "没有需要更新的内容"

        self._refresh_system_prompt()
        return msg

    def _refresh_system_prompt(self):
        """刷新系统提示词（基于最新记忆）"""
        pref_text, recent_text = self.user_memory.get_system_context()
        self.system_prompt = system_prompt_builder(
            tools_list=", ".join([t.name for t in self.tools + [self.update_memory_tool]]),
            pref_text=pref_text,
            recent_text=recent_text
        )
        # 重新创建 agent 以应用新提示词，但复用 checkpointer 保持跨轮次状态
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools + [self.update_memory_tool],
            system_prompt=self.system_prompt,
            checkpointer=self.checkpointer
        )

    def chat(self, user_input: str, is_streaming: bool = True):
        """多轮对话"""

        # 记录用户输入
        self.conversation_history.append({"role": "user", "content": user_input})

        if is_streaming:
            full_response = ""
            for chunk in self.agent.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                self.config,
                stream_mode="messages"
            ):
                if isinstance(chunk, tuple):
                    token, metadata = chunk
                    if token and token.content:
                        full_response += token.content
                        yield token.content
                        
            yield "\n"  # 最后换行
            # 记录助手回复
            self.conversation_history.append({"role": "assistant", "content": full_response})
            # 刷新系统提示词（下次对话生效）
            self._refresh_system_prompt()
            
        else:
            response = self.agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            self.config
        )
            assistant_msg = response['messages'][-1].content
            # 记录助手回复
            self.conversation_history.append({"role": "assistant", "content": assistant_msg})
            # 刷新系统提示词（下次对话生效）
            self._refresh_system_prompt()
            return assistant_msg
            


if __name__ == "__main__":
    print("=" * 40)
    print("欢迎使用随便 Agent！今天吃什么？")
    print("=" * 40)

    # 登录/注册
    while True:
        print("\n请选择：")
        print("1. 登录（已有账号）")
        print("2. 注册（新用户）")
        choice = input("请输入选项（1/2）：").strip()

        if choice == "1":
            user_id = input("请输入用户ID：").strip()
            memory_path = f"./users_history/{user_id}.json"
            if not os.path.exists(memory_path):
                print(f"用户 {user_id} 不存在，请先注册或检查输入是否正确。")
                continue
            print(f"登录成功！欢迎回来 {user_id}~")
            break
        elif choice == "2":
            user_id = input("请输入要注册的用户ID：").strip()
            memory_path = f"./users_history/{user_id}.json"
            if os.path.exists(memory_path):
                print(f"用户 {user_id} 已存在，请选择登录或更换ID。")
                continue
            # 创建新用户记忆文件
            UserMemoryManager(user_id)
            print(f"注册成功！欢迎新用户 {user_id}~")
            break
        else:
            print("无效选项，请重新输入。")

    # Agent 初始化
    agent = RecipeAgent(user_id=user_id, llm=llm, tools=tools)
    print("\n" + "=" * 40)
    print("开始对话吧！输入 exit 或 quit 退出程序。")
    print("=" * 40 + "\n")

    while True:
        user_input = input("你：")
        if user_input.lower() in ["exit", "quit"]:
            print("Bye bye~")
            break

        print("AI：", end="", flush=True)
        
        # 使用流式模式
        try:
            for chunk in agent.chat(user_input):
                print(chunk, end="", flush=True)
            print("\n\n")  # 换行
        except:
            response = agent.chat(user_input, is_streaming = False)
            print(response)
