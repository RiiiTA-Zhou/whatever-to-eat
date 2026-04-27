import gradio as gr
import requests
import re
from urllib.parse import unquote

import os

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")


def post_process_tool_output(text: str) -> str:
    """
    缩略工具输出：
    - 本地搜索：只显示菜名
    - 联网搜索：只显示标题
    """
    if not text:
        return text

    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # 检测分隔线
        if re.match(r'^-+$', line):
            # 收集完整的搜索结果块
            search_block = []
            i += 1
            while i < len(lines) and not re.match(r'^-+$', lines[i].strip()):
                search_block.append(lines[i])
                i += 1

            block_text = '\n'.join(search_block)

            # 提取所有菜名
            titles = re.findall(r'【菜名】(.+)', block_text)

            if titles:
                # 判断是本地搜索还是联网搜索
                # 本地搜索：菜名后紧跟【主要食材】
                # 联网搜索：菜名后跟"内容："
                if '内容：' in block_text:
                    result_lines.append(f"[联网搜索] 找到 {len(titles)} 个结果：")
                else:
                    result_lines.append(f"[本地知识库] 找到 {len(titles)} 个菜谱：")

                for t in titles[:3]:
                    result_lines.append(f"  • {t.strip()}")
                if len(titles) > 3:
                    result_lines.append(f"  ... 还有 {len(titles) - 3} 个")
            continue

        result_lines.append(lines[i])
        i += 1

    return '\n'.join(result_lines)


def register_user(user_id):
    """Register a new user and load preferences"""
    if not user_id.strip():
        return "错误: 请输入用户ID", "", "", "", 3, ""

    try:
        resp = requests.post(f"{API_BASE}/register", json={"user_id": user_id})
        data = resp.json()
        if resp.status_code == 200:
            status = f"✓ {data['message']}"
        else:
            status = f"错误: {data.get('detail', '注册失败')}"
            return status, "", "", "", 3, ""
    except requests.exceptions.ConnectionError:
        status = "错误: 无法连接到API服务，请确保 api.py 已启动"
        return status, "", "", "", 3, ""

    # Load preferences after register/login
    tastes, dislikes, avoid, difficulty, recent = load_preferences(user_id)
    return status, tastes, dislikes, avoid, difficulty, recent


def chat(user_id, message, history):
    """Send message and get streaming response"""
    if not user_id.strip():
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": "请先输入用户ID"})
        return history, ""
    if not message.strip():
        return history, ""

    history.append({"role": "user", "content": message})
    yield history, ""

    try:
        response = requests.post(
            f"{API_BASE}/chat",
            json={"user_id": user_id, "message": message},
            stream=True,
            headers={"Accept": "text/event-stream"}
        )

        full_response = ""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    full_response += unquote(line[6:])
                    if history and history[-1].get("role") == "assistant":
                        history[-1]["content"] = full_response
                    else:
                        history.append({"role": "assistant", "content": full_response})
                    yield history, ""
                elif full_response:
                    # 不是 data: 开头，说明是上一条的延续（换行），直接追加
                    full_response += "\n" + unquote(line)
                    if history and history[-1].get("role") == "assistant":
                        history[-1]["content"] = full_response
                    else:
                        history.append({"role": "assistant", "content": full_response})
                    yield history, ""

    except requests.exceptions.ConnectionError:
        if history and history[-1].get("role") == "assistant":
            history[-1]["content"] = "错误: 无法连接到API服务，请确保 api.py 已启动"
        else:
            history.append({"role": "assistant", "content": "错误: 无法连接到API服务，请确保 api.py 已启动"})
        yield history, ""
    except Exception as e:
        if history and history[-1].get("role") == "assistant":
            history[-1]["content"] = f"错误: {str(e)}"
        else:
            history.append({"role": "assistant", "content": f"错误: {str(e)}"})
        yield history, ""


def clear_chat():
    """Clear chat history"""
    return []


def load_preferences(user_id):
    """从API加载用户偏好"""
    if not user_id.strip():
        return "", "", "", 3, ""
    try:
        resp = requests.get(f"{API_BASE}/memory/{user_id}")
        if resp.status_code == 200:
            data = resp.json()
            prefs = data.get("preferences", {})
            tastes = "，".join(prefs.get("tastes", []))
            dislikes = "，".join(prefs.get("dislikes", []))
            avoid = "，".join(prefs.get("avoid", []))
            difficulty = prefs.get("difficulty_preference") or 3
            recent = ""
            for meal in data.get("recent_meals", []):
                recent += f"{meal['date']}: {meal['dish']}\n"
            return tastes, dislikes, avoid, difficulty, recent.strip()
        else:
            return "", "", "", 3, ""
    except Exception as e:
        print(f"加载偏好失败: {e}")
        return "", "", "", 3, ""


def parse_recent_meals(text: str) -> list:
    """将近期饮食文本解析为结构化列表"""
    meals = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            date, dish = line.split(":", 1)
            meals.append({"date": date.strip(), "dish": dish.strip()})
        else:
            # 没有日期，使用今日日期
            from datetime import datetime
            meals.append({"date": datetime.now().strftime("%Y-%m-%d"), "dish": line})
    return meals


def save_preferences(user_id, tastes, dislikes, avoid, difficulty, recent):
    """保存用户偏好到API"""
    if not user_id.strip():
        return "请先输入用户ID"
    try:
        tastes_list = [t.strip() for t in tastes.replace("，", ",").split(",") if t.strip()]
        dislikes_list = [d.strip() for d in dislikes.replace("，", ",").split(",") if d.strip()]
        avoid_list = [a.strip() for a in avoid.replace("，", ",").split(",") if a.strip()]

        payload = {
            "preferences": {
                "tastes": tastes_list,
                "dislikes": dislikes_list,
                "avoid": avoid_list,
                "difficulty_preference": int(difficulty) if difficulty else None
            },
            "recent_meals": parse_recent_meals(recent)
        }
        resp = requests.post(f"{API_BASE}/memory/{user_id}", json=payload)
        if resp.status_code == 200:
            return "✓ 偏好已保存"
        else:
            return f"错误: {resp.json().get('detail', '保存失败')}"
    except requests.exceptions.ConnectionError:
        return "错误: 无法连接到API服务"


def check_connection():
    """Check if API is running"""
    try:
        resp = requests.get(f"{API_BASE}/")
        if resp.status_code == 200:
            return "✓ API已连接"
        return "✗ API连接失败"
    except:
        return "✗ API未运行"


css = """
#title {text-align: center; font-size: 2em; font-weight: bold; margin-bottom: 0.5em;}
#subtitle {text-align: center; color: gray; margin-bottom: 1em;}
.status-bar {text-align: center; padding: 0.5em; font-size: 0.9em;}
"""

with gr.Blocks(title="随便吃 Agent") as demo:
    gr.HTML('<div id="title">🍜 随便吃 Agent</div>')
    gr.HTML('<div id="subtitle">今天吃什么？让AI帮你决定！</div>')

    with gr.Row():
        with gr.Column(scale=1):
            user_id_input = gr.Textbox(
                label="用户ID",
                placeholder="输入你的用户ID"
            )
            with gr.Row():
                register_btn = gr.Button("注册/登录", variant="primary")
                load_btn = gr.Button("加载偏好")

            status_text = gr.HTML('<div class="status-bar">状态: 未连接</div>')

            with gr.Accordion("用户偏好设置", open=True):
                tastes_input = gr.Textbox(
                    label="喜欢的口味",
                    placeholder="例: 清淡, 鲜香, 辣",
                    lines=2
                )
                dislikes_input = gr.Textbox(
                    label="不喜欢的食物",
                    placeholder="例: 太油腻的, 内脏",
                    lines=2
                )
                avoid_input = gr.Textbox(
                    label="忌口/过敏",
                    placeholder="例: 牛奶, 海鲜",
                    lines=2
                )
                difficulty_slider = gr.Slider(
                    minimum=1, maximum=5, step=1, value=3,
                    label="菜谱难度偏好",
                    info="1=新手小白 → 5=专业大厨"
                )
                recent_display = gr.Textbox(
                    label="近期饮食记录（每行格式：日期: 菜品，或直接输入菜品）",
                    placeholder="例：2026-04-27: 宫保鸡丁，米饭\n或直接输入：宫保鸡丁，米饭",
                    lines=4
                )
                save_btn = gr.Button("💾 保存偏好", variant="secondary")
                save_status = gr.HTML("")

            gr.HTML("<hr>")
            gr.HTML("**使用说明**<br>1. 输入用户ID点击注册<br>2. 在下方输入你想吃的东西<br>3. AI会帮你推荐和搜索菜谱")

        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="对话", height=500)
            msg_input = gr.Textbox(
                label="今天想吃什么？",
                placeholder="比如: 我想吃清淡的，有鸡肉的菜",
                lines=3
            )
            with gr.Row():
                send_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空对话")

    register_btn.click(
        fn=register_user,
        inputs=[user_id_input],
        outputs=[status_text, tastes_input, dislikes_input, avoid_input, difficulty_slider, recent_display]
    )

    load_btn.click(
        fn=load_preferences,
        inputs=[user_id_input],
        outputs=[tastes_input, dislikes_input, avoid_input, difficulty_slider, recent_display]
    )

    save_btn.click(
        fn=save_preferences,
        inputs=[user_id_input, tastes_input, dislikes_input, avoid_input, difficulty_slider, recent_display],
        outputs=[save_status]
    )

    send_btn.click(
        fn=chat,
        inputs=[user_id_input, msg_input, chatbot],
        outputs=[chatbot, msg_input]
    )

    msg_input.submit(
        fn=chat,
        inputs=[user_id_input, msg_input, chatbot],
        outputs=[chatbot, msg_input]
    )

    clear_btn.click(
        fn=clear_chat,
        outputs=chatbot
    )

    demo.load(fn=check_connection, outputs=[status_text])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, css=css)