import gradio as gr
import requests
import re
from urllib.parse import unquote

API_BASE = "http://localhost:8000"


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
    """Register a new user"""
    if not user_id.strip():
        return "错误: 请输入用户ID"

    try:
        resp = requests.post(f"{API_BASE}/register", json={"user_id": user_id})
        data = resp.json()
        if resp.status_code == 200:
            return f"✓ {data['message']}"
        else:
            return f"错误: {data.get('detail', '注册失败')}"
    except requests.exceptions.ConnectionError:
        return "错误: 无法连接到API服务，请确保 api.py 已启动"


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
            register_btn = gr.Button("注册/登录", variant="primary")
            status_text = gr.HTML('<div class="status-bar">状态: 未连接</div>')

            register_btn.click(
                fn=register_user,
                inputs=[user_id_input],
                outputs=[status_text]
            )

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