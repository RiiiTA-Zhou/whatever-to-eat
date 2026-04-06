import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from prompt_template import system_template

load_dotenv()

llm = ChatOpenAI(
    model = os.getenv("AGENT_MODEL_ID"),
    api_key = os.getenv("AGENT_API_KEY"),
    base_url = os.getenv("AGENT_BASE_URL"),
    temperature = 0.8,
    timeout = 40,
    streaming=True,
)

long_term_preferences = """
用户是广东人，但是喜欢微辣口味，不太喜欢甜食
用户喜欢炸物
"""
recent_history = """
用户最近吃了：
- 2026-04-06 吃了：牛肉棒
- 2026-04-01 吃了：烤肉，米饭
- 2026-03-31 吃了：烤菠菜，披萨
- 2026-03-30 吃了：猪扒波奇饭
- 2026-03-29 吃了：杀猪粉
- 2026-03-28 吃了：牛肉面
"""

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    MessagesPlaceholder(variable_name="messages"),
])

chain = chat_prompt | llm

message_list = []

print("今天吃什么？输入exit或quit退出程序。")

while True:
    user_input = input("你：")
    if user_input.lower() in ["exit", "quit"]:
        print("Bye bye~")
        break

    message_list.append(HumanMessage(content=user_input))

    response_stream = chain.stream({"long_term_preferences": long_term_preferences, "recent_history": recent_history, "messages": message_list})

    full_response = ""
    print("agent：", end="", flush=True)
    for chunk in response_stream:
        content = chunk.content
        print(content, end="", flush=True)
        full_response += content
    print()  # 新行

    message_list.append(AIMessage(content=full_response))


