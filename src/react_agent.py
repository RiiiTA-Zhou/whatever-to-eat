import os
import re
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from recipe_retrieval_tool import load_vector_store, dense_search, search_with_filters
from web_search_tool import web_search

load_dotenv()


class ReActAgent:
    """ReAct（推理+行动）代理，支持混合检索、Web搜索"""

    def __init__(
        self,
        model_id: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = 0.8,
        timeout: int = 40,
        max_iterations: int = 3,
        persist_directory: str = "./recipe_db",
        user_id: str = "user_ritazhou2121"
    ):
        """
        初始化 ReAct 代理。

        Args:
            model_id: LLM 模型ID
            api_key: API 密钥
            base_url: API 地址
            temperature: 模型温度
            timeout: 超时时间
            max_iterations: 最大迭代次数
            persist_directory: 向量库持久化目录
            user_id: 用户ID，用于加载用户偏好和历史
        """
        self.llm = ChatOpenAI(
            model=model_id or os.getenv("AGENT_MODEL_ID"),
            api_key=api_key or os.getenv("AGENT_API_KEY"),
            base_url=base_url or os.getenv("AGENT_BASE_URL"),
            temperature=temperature,
            timeout=timeout
        )
        
        self.max_iterations = max_iterations
        self.message_history = []
        self.vector_store = load_vector_store(persist_directory)
        user_history_file = os.path.join("users_history", user_id+".json")
        self.user_preferences, self.recent_meals = self._parse_history(user_history_file)
        
        # 工具定义，供 LLM 理解
        self.tool_definitions = [
            {
                "name": "search_recipes",
                "description": "从本地菜谱数据库中搜索相关菜谱",
                "parameters": {
                    "query": "搜索查询，如'清淡的鸡肉菜'，或'辣椒炒肉'"
                }
            },
            {
                "name": "search_recipes_with_filters",
                "description": "从本地菜谱数据库中搜索相关菜谱，支持难度，菜名关键词，关键材料等过滤条件",
                "parameters": {
                    "query": "搜索查询，如'清淡的鸡肉菜'，或'辣椒炒肉'",
                    "difficulty": "难度级别，1-5 数值，表示菜谱的难易程度",
                    "key_ingredients": "关键材料列表，如['鸡肉', '辣椒']"
                }
            },
            {
                "name": "web_search",
                "description": "通过网络搜索获取外部菜谱信息或餐厅信息",
                "parameters": {
                    "query": "搜索查询，如'猪肺汤 菜谱'，或'香辣 螃蟹 菜谱'"
                }
            },
            {
                "name": "recommend",
                "description": "根据用户需求和收集的信息生成最终的菜谱推荐",
                "parameters": {
                    "recommendation": '''直接生成推荐文本，符合以下格式要求：

菜谱名称：给出这顿饭都有什么菜，如米饭、炒青菜等

营养成分：给出碳水化合物、脂肪、蛋白质、膳食纤维的比例

所需时间：给出做饭预计所需要的时间，以分钟为单位

所需材料：列出所需的材料和重量

烹饪步骤：对每个菜肴给出详细的做饭步骤和说明，首先给出单个菜肴的名称，然后再用有序列表列出这个菜的操作步骤'''
                }
            }
        ]

    def _format_tool_definitions(self) -> str:
        """格式化工具定义供 LLM 使用"""
        return json.dumps(self.tool_definitions, ensure_ascii=False, indent=2)
    
    def _parse_history(self, history_file: str):
        """解析用户偏好记忆"""
        with open(history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        return history.get('preferences', ''), history.get('recent_meals', '')

    def _format_system_prompt(self) -> str:
        """生成系统提示词"""
        return f"""你是一个智能美食推荐助手，你非常了解营养学和饮食搭配。你可以使用以下工具，根据用户的输入的要求，用户偏好和近期饮食历史，来给用户推荐一顿饭的菜谱。

【可用工具】
{self._format_tool_definitions()}

【响应格式】
你必须按以下格式回应，每一步使用一行：
Thought: <你的推理，分析用户需求和应该采取的行动>
Action: <工具名称：search_recipes、search_recipes_with_filters、web_search>
Action Input: <工具参数，JSON 格式>

收到工具返回的结果后：
Observation: <工具执行结果>

然后继续下一步推理和行动。

【行动指南】
1. 如果用户查询明确（如"清淡菜"、"海鲜"），优先使用 search_recipes_with_filters 从本地数据库搜索；没有很明确的时候，直接用 search_recipes 搜索；如果用户要求外部信息（如"附近的餐厅"、"网红菜"），使用 web_search
3. 在收集足够信息后（最多3轮），使用 recommend 生成最终推荐
4. 推荐时考虑用户的长期偏好和最近的饮食历史

【用户饮食偏好】
{self.user_preferences}


【用户近期饮食】
{self.recent_meals}

【菜谱要求】
- 菜谱需要符合用户偏好和饮食习惯，且严禁给出用户过敏的食物，尽量不要给出用户避免的食物
- 菜谱尽量和用户近期历史不重复
- 菜谱需要符合营养学原理，符合健康饮食原则
- 菜谱需要包含一顿饭的内容，需要涵盖主食和1-3个菜肴

【重要提示】
- 只有当你确信有足够信息或已到达迭代上限时，才使用 recommend 工具
- 保持推理简洁，专注于用户的实际需求
- 如果搜索失败，直接给出基于常识的推荐
- 推荐菜谱后，当用户进一步询问具体的烹饪步骤时，你需要耐心细致地解答。当用户不满意这个菜谱时，你需要给出替换建议。"""

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 输出中的 Thought/Action/Action Input。

        Returns:
            包含 thought, action, action_input 的字典，或 None（如果解析失败）
        """
        try:
            # 提取 Thought
            thought_match = re.search(r"Thought:\s*(.+?)(?:Action:|$)", text, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else ""

            # 提取 Action
            action_match = re.search(r"Action:\s*(\w+)", text)
            if not action_match:
                return None
            action = action_match.group(1).strip()

            # 提取 Action Input
            input_match = re.search(r"Action Input:\s*(.+?)(?:\n|$)", text, re.DOTALL)
            action_input = input_match.group(1).strip() if input_match else "{}"

            # 尝试解析 JSON 格式的 action_input
            try:
                action_input_dict = json.loads(action_input)
            except json.JSONDecodeError:
                # 如果不是 JSON，则作为字符串处理
                action_input_dict = {"query": action_input}

            return {
                "thought": thought,
                "action": action,
                "action_input": action_input_dict
            }
        except Exception as e:
            print(f"[错误] 解析 LLM 输出失败: {e}")
            return None

    def _search_recipes_with_filters(self, query: str, difficulty: Optional[int] = None, ingredients: Optional[List[str]] = None) -> str:
        """执行菜谱搜索，支持过滤"""
        try:
            results = search_with_filters(
                self.vector_store,
                query=query,
                k=3,
                difficulty_level=difficulty,
                key_ingredients=ingredients
            )
           
            return results
        except Exception as e:
            return f"搜索失败: {str(e)}"
        
    def _search_recipes(self, query: str) -> str:
        """执行菜谱搜索"""
        try:
            results = dense_search(self.vector_store, query=query, k=3)
            return results
        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _web_search(self, query: str) -> str:
        """执行网络搜索"""
        try:
            return web_search(query)
        except Exception as e:
            return f"网络搜索失败: {str(e)}"


    def _execute_action(self, action: str, action_input: Dict[str, Any], iteration: int) -> str:
        """执行指定的工具"""
        print(f"  [行动 {iteration}] 执行: {action}")
        
        if action == "search_recipes_with_filters":
            query = action_input.get("query", "")
            difficulty = action_input.get("difficulty")
            ingredients = action_input.get("ingredients")
            result = self._search_recipes_with_filters(query, difficulty, ingredients)
        elif action == "search_recipes":
            query = action_input.get("query", "")
            result = self._search_recipes(query)
        elif action == "web_search":
            query = action_input.get("query", "")
            result = self._web_search(query)
        elif action == "recommend":
            # recommend 工具直接返回推荐文本，不执行外部函数
            result = action_input.get("recommendation", "未提供推荐内容")
        else:
            result = f"未知的工具: {action}"
        
        return result

    def run(self) -> str:
        """
        执行 ReAct 循环。

        Args:
            user_query: 用户查询

        Returns:
            最终推荐文本
        """
        self.message_raw_list = []
        self.react_history = []
        
        # 构建初始提示词
        system_prompt = self._format_system_prompt()
        self.message_raw_list.append(SystemMessage(content=system_prompt))
        self.react_history.append(f"system: {system_prompt}")
        

        print("今天吃什么？输入exit或quit退出程序。")
        
        while True:
            user_query = input("你：")
            if user_query.lower() in ["exit", "quit"]:
                print("Bye bye~")
                break

            self.message_raw_list.append(HumanMessage(content=user_query))

            user_message = f"""用户查询：{user_query}"""

            iteration = 0
            final_recommendation = None
            
            while iteration < self.max_iterations:
                iteration += 1
                print(f"\n[迭代 {iteration}/{self.max_iterations}]")
                
                llm_output = ""
                try:
                    response = self.llm.invoke(self.message_raw_list)
                    llm_output = response.content
                    self.message_raw_list.append(AIMessage(content=llm_output))
                    print(f"llm 输出:\n{llm_output}")
                except Exception as e:
                    print(f"  [错误] LLM 调用失败: {e}")
                    break
                
                # 解析 LLM 输出
                parsed = self._parse_tool_call(llm_output)
                if not parsed:
                    print(f"  [警告] 无法解析 LLM 输出")
                    final_recommendation = llm_output
                    break
                
                thought = parsed["thought"]
                action = parsed["action"]
                action_input = parsed["action_input"]
                
                # 记录 Thought 和 Action
                self.react_history.append(f"Thought: {thought}")
                self.react_history.append(f"Action: {action}\nAction Input: {json.dumps(action_input, ensure_ascii=False)}")
                
                # 执行 Action
                observation = self._execute_action(action, action_input, iteration)
                self.react_history.append(f"Observation: {observation}")
                
                # 如果是 recommend 动作或达到迭代上限，则停止
                if action == "recommend" or iteration >= self.max_iterations:
                    final_recommendation = observation
                    break
                else:
                    # 将 Observation 添加到消息列表，供下一轮 LLM 使用
                    self.message_raw_list.append(ToolMessage(content=f"Observation: {observation}"))
                    
                print(f"  [观察] {observation}")
            
            if not final_recommendation:
                final_recommendation = "抱歉，无法生成推荐。请重试。"
            
            print(f"agent: {final_recommendation}")


if __name__ == "__main__":
    agent = ReActAgent()
    agent.run()
