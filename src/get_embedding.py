import json
import re
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import os

load_dotenv()

def load_and_prepare_recipes(json_file_path: str) -> list[Document]:
    """加载 JSON 菜谱并转换为 Document 对象"""
     
    with open(json_file_path, 'r', encoding='utf-8') as f:
        recipes = json.load(f)
    
    # 如果是单条 JSON 对象，先包装成列表
    if isinstance(recipes, dict):
        recipes = [recipes]
    
    documents = []
    
    for recipe in recipes:
        # === 1. 构建用于 Embedding 的文本（核心）===
        # 策略：把菜名 + 关键食材 + 步骤要点 组合成自然语言
        embedding_text = build_embedding_text(recipe)
        
        # === 2. 提取元数据（用于过滤和展示）===
        metadata = extract_metadata(recipe)
        
        doc = Document(
            page_content=embedding_text,
            metadata=metadata
        )
        documents.append(doc)
    
    return documents

def build_embedding_text(recipe: dict) -> str:
    """构建用于向量化的文本，这是检索效果的关键"""
    
    parts = []
    
    # 1. 菜名（权重最高，放在最前面）
    parts.append(f"【菜名】{recipe.get('dish_name', '')}")

    
    # 3. 关键食材（从 key_ingredients 中提取）
    ingredients = recipe.get('ingreditent_list', '')
    if ingredients:
        parts.append(f"【主要食材】{ingredients}")
    
    # 4. 做法摘要（提取步骤中的关键动作）
    steps_summary = recipe.get('recipe', '')
    if steps_summary:
        parts.append(f"【做法】{steps_summary}")
    
    # 5. 如果有 description，也加上
    if recipe.get('description'):
        parts.append(f"【简介】{recipe['description']}")
    
    return '\n'.join(parts)


def extract_metadata(recipe: dict) -> dict:
    """提取元数据，用于后续过滤检索"""
    
    # 解析难度（将星星转换为数值）
    difficulty_stars = recipe.get('difficulty', '')
    difficulty_level = len(difficulty_stars) if '★' in difficulty_stars else 0

    key_ingredients = recipe.get('key_ingredients', '')
    key_ingredients = [ing.strip() for ing in key_ingredients.split(',')] if key_ingredients else []
        
    return {
        "id": recipe.get('id', ''),
        "dish_name": recipe.get('dish_name', ''),
        "description": recipe.get('description', ''),
        "difficulty_level": difficulty_level,  # 1-5 数值，便于过滤
        "key_ingredients": key_ingredients,
        "source_file": "recipes.json"
    }

# ============ 主流程 ============

def create_recipe_vector_store(
    json_file_path: str,
    persist_directory: str = "./recipe_db"
):
    """创建菜谱向量数据库"""
    
    # 加载并转换数据
    print("正在加载菜谱数据...")
    documents = load_and_prepare_recipes(json_file_path)
    print(f"加载了 {len(documents)} 个菜谱")

    
    # 3. 选择 Embedding 模型：OpenAI
    embeddings = OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_ID"),
        api_key=os.getenv("EMBEDDING_API_KEY"),
        base_url=os.getenv("EMBEDDING_BASE_URL"),
        dimensions=1024
    )
    
    # 4. 创建向量库
    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    print(f"向量库已保存到 {persist_directory}")
    return vector_store

# ============ 使用示例 ============

if __name__ == "__main__":
    # 创建向量库
    vector_store = create_recipe_vector_store(
        json_file_path="./data/recipes.json",
        persist_directory="./recipe_db"
    )
    
    # 测试检索
    results = vector_store.similarity_search(
        "想吃清淡的鸡", 
        k=5
    )
    
    for doc in results:
        print(f"\n菜名: {doc.metadata['dish_name']}")
        print(f"难度: {doc.metadata['difficulty_level']}")
        print(f"内容预览: {doc.page_content[:100]}...")