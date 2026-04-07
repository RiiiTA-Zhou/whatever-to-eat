from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    api_key=os.getenv("EMBEDDING_API_KEY"),
    base_url=os.getenv("EMBEDDING_BASE_URL")
)

try:
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input="测试文本",
        dimensions=1024
    )
    print("✅ API Key 正常，返回了 embedding 数据")
    print(response)
    print(f"向量维度: {len(response.data[0].embedding)}")
except Exception as e:
    print(f"❌ API 调用失败: {e}")
    print(f"错误类型: {type(e)}")