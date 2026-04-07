import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import Tool
from recipe_retrieval_tool import load_vector_store, dense_search, search_with_filters
from web_search_tool import web_search

load_dotenv()

# =========== 定义工具 ===========

vector_store = load_vector_store()

@tool
def search_recipes_with_filters(query: str, difficulty: Optional[int] = None, ingredients: Optional[list[str]] = None) -> str:
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


