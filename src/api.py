import os
import sys
from pathlib import Path
from urllib.parse import quote

# 将 src 目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from whatever_agent import RecipeAgent, llm, tools


# =========== Agent 缓存（每个用户一个实例） ===========

agent_cache: dict[str, RecipeAgent] = {}


def get_or_create_agent(user_id: str) -> RecipeAgent:
    """获取或创建用户对应的 agent 实例"""
    if user_id not in agent_cache:
        agent_cache[user_id] = RecipeAgent(
            user_id=user_id,
            llm=llm,
            tools=tools
        )
    return agent_cache[user_id]


# =========== Pydantic Models ===========

class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    user_id: str
    response: str


class RegisterRequest(BaseModel):
    user_id: str


# =========== FastAPI App ===========

app = FastAPI(
    title="随便吃 Agent API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "随便吃 Agent API", "version": "1.0.0"}


@app.post("/register")
async def register(req: RegisterRequest):
    """Register a new user"""
    from user_memory import UserMemoryManager

    user_id = req.user_id
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    memory_path = f"./users_history/{user_id}.json"
    if os.path.exists(memory_path):
        return {"status": "exists", "user_id": user_id, "message": f"用户 {user_id} 已存在"}

    UserMemoryManager(user_id)
    return {"status": "created", "user_id": user_id, "message": f"新用户 {user_id} 创建成功"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Stream chat response"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    agent = get_or_create_agent(req.user_id)

    def generate():
        for token in agent.chat_stream(req.message):
            if token:
                yield f"data: {quote(token, safe='')}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"}
    )


@app.post("/chat_sync")
async def chat_sync(req: ChatRequest):
    """Non-streaming chat response"""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    agent = get_or_create_agent(req.user_id)
    response = agent.chat(req.message)

    return ChatResponse(user_id=req.user_id, response=response)


@app.get("/memory/{user_id}")
async def get_memory(user_id: str):
    """Get user memory/preferences"""
    from user_memory import UserMemoryManager
    memory_manager = UserMemoryManager(user_id)
    return memory_manager.memory


@app.post("/memory/{user_id}")
async def update_memory(user_id: str, data: dict):
    """Update user memory/preferences"""
    from user_memory import UserMemoryManager
    memory_manager = UserMemoryManager(user_id)

    prefs = data.get("preferences", {})
    if "tastes" in prefs:
        memory_manager.memory["preferences"]["tastes"] = prefs["tastes"]
    if "dislikes" in prefs:
        memory_manager.memory["preferences"]["dislikes"] = prefs["dislikes"]
    if "avoid" in prefs:
        memory_manager.memory["preferences"]["avoid"] = prefs["avoid"]
    if "difficulty_preference" in prefs:
        memory_manager.memory["preferences"]["difficulty_preference"] = prefs["difficulty_preference"]

    if "recent_meals" in data:
        memory_manager.memory["recent_meals"] = data["recent_meals"]

    memory_manager._save()
    # Also refresh agent's system prompt if it exists
    agent = agent_cache.get(user_id)
    if agent:
        agent._refresh_system_prompt()

    return {"status": "ok", "message": "偏好已更新"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)