import os
import sys
from pathlib import Path

# 将 src 目录添加到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from whatever_agent import RecipeAgent, llm, tools


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

    agent = RecipeAgent(user_id=req.user_id, llm=llm, tools=tools)

    def generate():
        for token in agent.chat(req.message, is_streaming=True):
            if token:
                yield f"data: {token}\n\n"

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

    agent = RecipeAgent(user_id=req.user_id, llm=llm, tools=tools)
    response = agent.chat(req.message, is_streaming=False)

    return ChatResponse(user_id=req.user_id, response=response)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)