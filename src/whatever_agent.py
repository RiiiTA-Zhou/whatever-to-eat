import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from recipe_retrieval_tool import load_vector_store, dense_search, search_with_filters
from web_search_tool import web_search
from user_memory import UserMemoryManager
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

load_dotenv()

# =========== 定义工具 ===========

vector_store = load_vector_store()

@tool
def search_recipes_with_filters(query: str, difficulty: int | None = None, ingredients: list[str] | None = None) -> str:
    """从本地数据库搜索菜谱，支持难度和食材过滤
    
    Args:
        query: 搜索关键词，如'清淡的鸡肉菜'，或'辣椒炒肉'
        difficulty: 难度级别，1-5
        ingredients: 关键食材列表，至少一个"""
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
        query: 搜索关键词，如'猪肺汤 菜谱'，或'香辣 螃蟹 菜谱'"""
    try:
        return web_search(query)
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

        pref_text, recent_text = self.user_memory.get_system_context()
        self.system_prompt = \
f"""你是一个智能美食推荐助手，你非常了解营养学和饮食搭配。你可以使用以下工具，根据用户的输入的要求，用户偏好和近期饮食历史，来给用户推荐一顿饭的菜谱。

【可用工具】
{', '.join([tool.name for tool in tools])}

【响应格式】
你必须按以下格式回应，每一步使用一行：
Thought: <你的推理，分析用户需求和应该采取的行动>
Action: <工具名称：search_recipes、search_recipes_with_filters、web_search>
Action Input: <工具参数，JSON 格式>

收到工具返回的结果后：
Observation: <工具执行结果>

然后继续下一步推理和行动。

【行动指南】
1. 如果用户查询明确（如"清淡菜"、"海鲜"），优先使用 search_recipes_with_filters 从本地数据库搜索；需求较为模糊的时候，直接用 search_recipes 搜索；如果用户要求外部信息（如"附近的餐厅"、"网红菜"）或本地搜索失败，使用 web_search
2. 生成查询以调用工具时，尽量不要使用否定表示，如“不辣”，而是用“清淡”来表达。
3. 在收集足够信息后返回推荐；如果所有搜索失败，则基于自己的知识给出推荐

【用户饮食偏好】
{pref_text}


【用户近期饮食】
{recent_text}

【菜谱要求】
- 菜谱需要符合用户偏好和饮食习惯，且严禁给出用户忌口的食物，减少给出用户不喜欢的事物
- 菜谱尽量和用户近期历史避免过度重复，保证饮食多样性
- 菜谱需要符合营养学原理，符合健康饮食原则
- 菜谱需要包含一顿饭的内容，需要涵盖主食和1-3个菜肴，荤素搭配

"""
        # 用于保持同一用户的对话记忆
        self.config = {"configurable": {"thread_id": user_id}}

        self.agent = create_agent(
            model = self.llm,
            tools = self.tools,
            system_prompt = self.system_prompt,
            checkpointer = InMemorySaver()
        )

        
    def chat(self, user_input: str) -> str:
        """多轮对话"""
        
        # 调用时传入 输入
        response = self.agent.invoke(
            {"message": [{"role": "user", "content": user_input}]},
            self.config)
        
        return response

                

# chat_prompt = ChatPromptTemplate.from_messages([
#     ("system", system_template),
#     MessagesPlaceholder(variable_name="messages"),
# ])

# chain = chat_prompt | llm

# message_list = []

# print("今天吃什么？输入exit或quit退出程序。")

# while True:
#     user_input = input("你：")
#     if user_input.lower() in ["exit", "quit"]:
#         print("Bye bye~")
#         break

#     message_list.append(HumanMessage(content=user_input))

#     response_stream = chain.stream({"long_term_preferences": long_term_preferences, "recent_history": recent_history, "messages": message_list})

#     full_response = ""
#     print("agent：", end="", flush=True)
#     for chunk in response_stream:
#         content = chunk.content
#         print(content, end="", flush=True)
#         full_response += content
#     print()  # 新行

#     message_list.append(AIMessage(content=full_response))


if __name__ == "__main__":
    user_id = "test123"
    agent = RecipeAgent(user_id=user_id, llm=llm, tools=tools)
    while True:
        user_input = input("你：")
        if user_input.lower() in ["exit", "quit"]:
            print("Bye bye~")
            break
        
        response = agent.chat(user_input)
        print("agent：", response)
