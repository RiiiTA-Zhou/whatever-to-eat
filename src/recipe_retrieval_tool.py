from dotenv import load_dotenv
import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

load_dotenv()

def load_vector_store(persist_directory: str = "./recipe_db"):
    """加载已保存的向量数据库"""
    
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",
        dimensions=1024,
        openai_api_key=os.getenv("EMBEDDING_API_KEY"),
        openai_api_base=os.getenv("EMBEDDING_BASE_URL")
    )
    
    # 加载持久化的向量库
    vector_store = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    
    print(f"向量库已加载，包含 {vector_store._collection.count()} 个文档")
    return vector_store

def dense_search(vector_store, query: str, k: int = 3):
    """语义检索，返回最相似的 k 个菜谱"""
    
    results = vector_store.similarity_search_with_score(
        query=query,
        k=k
    )

    if not results:
        return "未找到符合条件的菜谱信息"
    
    return format_search_results(results)

def search_with_filters(
    vector_store, 
    query: str, 
    k: int = 3,
    difficulty_level: int = None,      # 难度级别：1-5
    dish_name_keyword: str = None,     # 菜名关键词
    key_ingredients: list = None,       # 关键材料
):
    """带条件过滤的语义检索"""
    
    # 构建过滤条件
    conditions = []
    filter_dict = None
    
    if difficulty_level:
        conditions.append({"difficulty_level": {"$lte": difficulty_level}})
    
    if dish_name_keyword:
        # 注意：Chroma 不支持模糊匹配，只能用 $eq 精确匹配
        # 如果需要模糊匹配，建议用 $contains 操作符（部分版本支持）
        conditions.append({"dish_name": {"$contains": dish_name_keyword}})
    
    if key_ingredients:
        for ingredient in key_ingredients:
            conditions.append({"key_ingredients": {"$contains": ingredient}})

    if len(conditions) == 1:
        filter_dict = conditions[0]
    else:
        filter_dict = {"$and": conditions}
    
    # 执行带过滤的检索
    results = vector_store.similarity_search_with_score(
        query=query,
        k=k,
        filter=filter_dict if filter_dict else None
    )

    if not results:
        return "未找到符合条件的菜谱信息"
    
    return format_search_results(results)

def format_search_results(retrieval_results: list) -> str:
    """格式化检索结果"""
    
    formatted_results = []
    for doc, score in retrieval_results:
        formatted_results.append(doc.page_content)
        formatted_results.append("\n" + "-"*40 + "\n")

    return "\n".join(formatted_results)

if __name__ == "__main__":
    query = "我想吃点辣的鸡肉"

    vector_store = load_vector_store(persist_directory="./recipe_db")

    print("---语义检索---")
    results = dense_search(vector_store, query, k=3)
    print(format_search_results(results))

    print("---带过滤的检索---")
    results = search_with_filters(
        vector_store,
        query=query,
        k=3,
        key_ingredients=["鸡", "辣椒"]
    )

    print(f"找到 {len(results)} 个符合条件的菜谱：")
    print(format_search_results(results))