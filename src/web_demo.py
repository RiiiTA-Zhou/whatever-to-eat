import gradio as gr
import requests

API_BASE = "http://localhost:8000"


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
        return history
    if not message.strip():
        return history

    history.append({"role": "user", "content": message})
    yield history

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
                    full_response += line[6:]
                    if history and history[-1].get("role") == "assistant":
                        history[-1]["content"] = full_response
                    else:
                        history.append({"role": "assistant", "content": full_response})
                    yield history

    except requests.exceptions.ConnectionError:
        if history and history[-1].get("role") == "assistant":
            history[-1]["content"] = "错误: 无法连接到API服务，请确保 api.py 已启动"
        else:
            history.append({"role": "assistant", "content": "错误: 无法连接到API服务，请确保 api.py 已启动"})
        yield history
    except Exception as e:
        if history and history[-1].get("role") == "assistant":
            history[-1]["content"] = f"错误: {str(e)}"
        else:
            history.append({"role": "assistant", "content": f"错误: {str(e)}"})
        yield history


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
                placeholder="输入你的用户ID",
                value="demo_user"
            )
            register_btn = gr.Button("注册/登录", variant="primary")
            status_text = gr.HTML('<div class="status-bar">状态: 未连接</div>')

            register_btn.click(
                fn=register_user,
                inputs=[user_id_input],
                outputs=[status_text]
            )

            gr.HTML("<hr>")
            gr.HTML("**使用说明**\n1. 输入用户ID点击注册\n2. 在下方输入你想吃的东西\n3. AI会帮你推荐和搜索菜谱")

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
        outputs=chatbot
    )

    msg_input.submit(
        fn=chat,
        inputs=[user_id_input, msg_input, chatbot],
        outputs=chatbot
    )

    clear_btn.click(
        fn=clear_chat,
        outputs=chatbot
    )

    demo.load(fn=check_connection, outputs=[status_text])

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, css=css)