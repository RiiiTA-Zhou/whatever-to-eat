import json
import os
import sqlite3
from datetime import datetime
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv


# =========== 数据库 Schema ===========

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    tastes TEXT NOT NULL DEFAULT '[]',
    dislikes TEXT NOT NULL DEFAULT '[]',
    avoid TEXT NOT NULL DEFAULT '[]',
    difficulty_preference INTEGER DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recent_meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    date TEXT NOT NULL,
    dish TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recent_meals_user_date
    ON recent_meals(user_id, date DESC);
"""


# =========== 用户记忆管理器 ===========
class UserMemoryManager:
    """管理用户的持久化记忆（SQLite 存储）"""

    def __init__(self, user_id: str, db_path: str = "./user_memory/whatever_to_eat.db"):
        self.user_id = user_id
        self._db_path = db_path

        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._init_db()

        self.memory = self._load()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        conn = self._connect()
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        conn.close()

    def _load(self) -> dict:
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT tastes, dislikes, avoid, difficulty_preference FROM users WHERE user_id = ?",
            (self.user_id,),
        )
        row = cursor.fetchone()

        if row:
            prefs = {
                "tastes": json.loads(row[0]),
                "dislikes": json.loads(row[1]),
                "avoid": json.loads(row[2]),
                "difficulty_preference": row[3],
            }
            cursor.execute(
                "SELECT date, dish FROM recent_meals WHERE user_id = ? ORDER BY id DESC LIMIT 30",
                (self.user_id,),
            )
            meals = [{"date": r[0], "dish": r[1]} for r in cursor.fetchall()]
            conn.close()
            return {"user_id": self.user_id, "preferences": prefs, "recent_meals": meals}

        default = {
            "user_id": self.user_id,
            "preferences": {
                "tastes": [],
                "dislikes": [],
                "avoid": [],
                "difficulty_preference": None,
            },
            "recent_meals": [],
        }
        cursor.execute(
            "INSERT INTO users (user_id, tastes, dislikes, avoid, difficulty_preference) VALUES (?, ?, ?, ?, ?)",
            (self.user_id, "[]", "[]", "[]", None),
        )
        conn.commit()
        conn.close()
        return default

    def _save(self):
        conn = self._connect()
        prefs = self.memory["preferences"]
        conn.execute(
            """INSERT INTO users (user_id, tastes, dislikes, avoid, difficulty_preference, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   tastes = excluded.tastes,
                   dislikes = excluded.dislikes,
                   avoid = excluded.avoid,
                   difficulty_preference = excluded.difficulty_preference,
                   updated_at = CURRENT_TIMESTAMP""",
            (
                self.user_id,
                json.dumps(prefs["tastes"], ensure_ascii=False),
                json.dumps(prefs["dislikes"], ensure_ascii=False),
                json.dumps(prefs["avoid"], ensure_ascii=False),
                prefs["difficulty_preference"],
            ),
        )
        conn.commit()
        conn.close()

    def get_system_context(self):
        """生成用于 SystemMessage 的上下文文本"""
        prefs = self.memory["preferences"]
        recent = self.memory["recent_meals"]

        preference_text = []

        if prefs.get("tastes"):
            preference_text.append(f"用户喜欢这些口味：{', '.join(prefs['tastes'])}")
        if prefs.get("dislikes"):
            preference_text.append(f"用户不喜欢：{', '.join(prefs['dislikes'])}")
        if prefs.get("avoid"):
            preference_text.append(f"用户忌口：{', '.join(prefs['avoid'])}")
        if prefs.get("difficulty_preference"):
            preference_text.append(f"用户偏好难度：{prefs['difficulty_preference']}（1小白都会→5超级大厨）")

        preference_text = "\n".join(preference_text)

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
                if new_prefs.get("tastes") is not None:
                    self.memory["preferences"]["tastes"] = new_prefs["tastes"]
                if new_prefs.get("dislikes") is not None:
                    self.memory["preferences"]["dislikes"] = new_prefs["dislikes"]
                if new_prefs.get("avoid") is not None:
                    self.memory["preferences"]["avoid"] = new_prefs["avoid"]
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
        conn = self._connect()

        cursor = conn.execute(
            "SELECT id, dish FROM recent_meals WHERE user_id = ? AND date = ? ORDER BY id DESC LIMIT 1",
            (self.user_id, today),
        )
        row = cursor.fetchone()

        if row:
            existing = row[1]
            for dish_name in dish_list:
                if dish_name not in existing:
                    existing = f"{existing}，{dish_name}"
            conn.execute("UPDATE recent_meals SET dish = ? WHERE id = ?", (existing, row[0]))
        else:
            conn.execute(
                "INSERT INTO recent_meals (user_id, date, dish) VALUES (?, ?, ?)",
                (self.user_id, today, ", ".join(dish_list)),
            )

        conn.execute(
            """DELETE FROM recent_meals WHERE user_id = ? AND id NOT IN (
                SELECT id FROM recent_meals WHERE user_id = ? ORDER BY id DESC LIMIT 30
            )""",
            (self.user_id, self.user_id),
        )
        conn.commit()

        cursor = conn.execute(
            "SELECT date, dish FROM recent_meals WHERE user_id = ? ORDER BY id DESC LIMIT 30",
            (self.user_id,),
        )
        self.memory["recent_meals"] = [{"date": r[0], "dish": r[1]} for r in cursor.fetchall()]
        conn.close()

    @staticmethod
    def user_exists(user_id: str, db_path: str = "./user_memory/whatever_to_eat.db") -> bool:
        """检查用户是否已存在"""
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA_SQL)
        cursor = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.commit()
        conn.close()
        return exists

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

    conversation = '''
用户：我最近想吃点清淡的东西，不太想吃辣的了。
助手：好的，我会记住你现在喜欢清淡口味，暂时不喜欢辣的了。还有其他口味或者饮食习惯需要我记住吗？
用户：嗯，还有我最近发现牛奶过敏。
'''
    user_memory.update_from_conversation(conversation_text=conversation)
    pref_text, recent_text = user_memory.get_system_context()
    print("更新后偏好：", pref_text)
    print("更新后近期饮食：", recent_text)
