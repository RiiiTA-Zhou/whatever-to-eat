import json
import os
from datetime import datetime
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv


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
        else:
            recent_text = ""

        return preference_text, recent_text
    
    def update_from_conversation(self, conversation_text: str):
        """从对话中提取并更新用户偏好（调用 LLM 提取）"""

        load_dotenv()

        llm = ChatOpenAI(
            model=os.getenv("AGENT_MODEL_ID"),
            api_key=os.getenv("AGENT_API_KEY"),
            base_url=os.getenv("AGENT_BASE_URL"),
            temperature=0.3,
            timeout=40,
            streaming=False,
        )

        prompt = f"""分析以下对话，提取用户的饮食偏好变化。

【重要规则：处理矛盾偏好】
- 如果用户明确说"想要X"或"想吃X"，但之前有相反的偏好Y，则用X替换Y
- 常见矛盾对（不能同时存在）：
  - 清淡 ↔ 辣/重口/油腻
  - 素食 ↔ 荤菜/肉
  - 甜 ↔ 咸
- 如果用户只是闲聊而没有表达明确的饮食偏好变化，则返回null表示不需要更新

对话：
{conversation_text}

现有偏好：
{json.dumps(self.memory["preferences"], ensure_ascii=False, indent=2)}

请分析并输出 JSON 格式的更新结果：
{{
    "update_needed": true或false，表示是否有明确的偏好变化需要更新，
    "preferences": {{
        "tastes": ["口味列表，如果update_needed为false则填null"],
        "dislikes": ["不喜欢列表，如果update_needed为false则填null"],
        "avoid": ["忌口列表，如果update_needed为false则填null"],
        "difficulty": 厨艺水平，1为厨房小白，5为专业厨师级别，数字1-5或null
    }}
}}

只输出 JSON，不要其他内容。"""

        try:
            response = llm.invoke(prompt)
            response_text = response.content.strip()
            if "```json" in response.content:
                response_text = response.content.split("```json")[-1].split("```")[0].strip()
            response_text = response_text.replace("```", "").strip()
            result = json.loads(response_text)

            if result.get("update_needed") and result.get("preferences"):
                new_prefs = result["preferences"]
                # 只更新有值的字段，保持字段名兼容
                if new_prefs.get("tastes") is not None:
                    self.memory["preferences"]["tastes"] = new_prefs["tastes"]
                if new_prefs.get("dislikes") is not None:
                    self.memory["preferences"]["dislikes"] = new_prefs["dislikes"]
                if new_prefs.get("avoid") is not None:
                    self.memory["preferences"]["avoid"] = new_prefs["avoid"]
                # 兼容 "difficulty" 和 "difficulty_preference" 两种字段名
                if new_prefs.get("difficulty") is not None:
                    self.memory["preferences"]["difficulty_preference"] = new_prefs["difficulty"]
                elif new_prefs.get("difficulty_preference") is not None:
                    self.memory["preferences"]["difficulty_preference"] = new_prefs["difficulty_preference"]
                self._save()
                return "已根据对话更新用户偏好"
            return "对话中没有需要更新的偏好变化"
        except Exception as e:
            return f"更新偏好失败: {e}"
    
    def add_recent_meal(self, dish_list: list[str]):
        """添加近期饮食记录"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 检查今天是否已记录
        recent = self.memory["recent_meals"]
        if recent and recent[0]["date"] == today:
            # 今天已有记录，合并
            existing = recent[0]["dish"]
            for dish_name in dish_list:
                if dish_name not in existing:
                    recent[0]["dish"] = f"{existing}，{dish_name}"
        else:
            # 新增记录
            recent.insert(0, {
                "date": today,
                "dish": ", ".join(dish_list)
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


if __name__ == "__main__":
    user_memory = UserMemoryManager("test123")
    print(user_memory.memory)

    # print("偏好文本：", pref_text)
    # print("近期饮食：", recent_text)
    # print("手动添加新偏好：喜欢辣口")
    # user_memory.add_preference("tastes", "辣口")
    # print("更新后偏好：", user_memory.memory["preferences"])
    # print("添加今日饮食：咖喱鸡扒蛋包饭")
    # user_memory.add_recent_meal(["咖喱鸡扒蛋包饭"])
    # pref_text, recent_text = user_memory.get_system_context()
    # print("更新后近期饮食：", recent_text)
    # print("更新后偏好：", user_memory.memory["preferences"])
    conversation = '''
用户：我最近想吃点清淡的东西，不太想吃辣的了。
助手：好的，我会记住你现在喜欢清淡口味，暂时不喜欢辣的了。还有其他口味或者饮食习惯需要我记住吗？
用户：嗯，还有我最近发现牛奶过敏。
'''
    user_memory.update_from_conversation(conversation_text=conversation)
    pref_text, recent_text = user_memory.get_system_context()
    print("更新后偏好：", pref_text)
    print("更新后近期饮食：", recent_text)