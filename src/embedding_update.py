'''
    更新Chroma向量数据库用的脚本
'''
from recipe_retrieval_tool import load_vector_store
import json
from langchain_core.documents import Document

def quick_update(dish_id: str, new_content: dict):
    """快速更新向量数据库中的文档内容
    
    Args:
        dish_id: 要更新的菜品 ID
        new_content: 包含新的菜谱信息的字典，结构应与原数据一致"""
    
    vector_store = load_vector_store(persist_directory="./recipe_db")
    
    # 构建新的文本和元数据
    from get_embedding import build_embedding_text, extract_metadata
    embedding_text = build_embedding_text(new_content)
    metadata = extract_metadata(new_content)

    updated_doc = Document(
                page_content=embedding_text,
                metadata=metadata
            )
    
    try:
        results = vector_store.get(
            where={"id": dish_id}
        )
        if results and results['ids']:
            actual_id = results['ids'][0]
            print(f"找到文档，实际 ID: {actual_id}")
            print(f"菜名: {results['metadatas'][0].get('dish_name')}")
            vector_store.update_documents(documents=[updated_doc], ids=[actual_id])
            print("文档更新成功！")

    except Exception as e:
        print(f"失败: {e}")
        return


if __name__ == "__main__":
    dish_id = "staple-煮锅蒸米饭"  # 替换为你要更新的菜品 ID
    new_content = {
        "id": "staple-煮锅蒸米饭",
        "dish_name": "煮锅蒸米饭",
        "description": "**煮锅蒸米饭**属于**主食**类别，口感软糯适中，米香浓郁。利用煮锅小火焖蒸，底部微带焦香而不粘。适合家庭日常、一人食或露营场景，简单省心，搭配炒菜、炖肉都很美味。",
        "difficulty": "★★",
        "key_ingredients": "大米",
        "recipe": "- 清洗大米\n- 将米和水加入煮锅\n- 大火煮至水沸腾\n- **搅拌底部防止粘黏**\n- 盖上锅盖，转**小火**加热 10-15 分钟（根据对软糯程度的喜好），中途切勿打开锅盖\n- 关火，静置 5 分钟\n- Enjoy :)",
        "ingreditent_list": "- 米：100ml-200ml/人\n- 水：米的体积的 2 倍"
    }

    
    quick_update(dish_id, new_content)