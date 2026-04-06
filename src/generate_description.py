prompt = \
'''
你是一个美食专家，专门为用户提供菜品的详细描述。请根据提供的菜谱生成一段关于菜品的描述，包括菜品的口味、所属类别(海鲜、荤菜、素菜、早餐、饮料等)、适合的食用场景等信息，尽量在100字以内。

{recipe}'''

import json

from utils import OpenAIModel, LLMConfig
from dotenv import load_dotenv
import os
from tqdm import tqdm

load_dotenv()

dpsk = LLMConfig(api_key=os.getenv("LLM_API_KEY"), llm_name=os.getenv("LLM_MODEL_ID"), base_url=os.getenv("LLM_BASE_URL"))
llm = OpenAIModel(dpsk)

def generate_description(recipe):
    prompt_with_recipe = prompt.format(recipe=recipe)
    description = llm.generate(prompt_with_recipe)
    return description.strip()

def main():
    with open('recipes.json', 'r', encoding='utf-8') as f:
        recipes = json.load(f)
    
    results = []
    for recipe in tqdm(recipes, desc="Generating descriptions"):
        desc = generate_description(recipe['recipe'])
        result = recipe.copy()
        result['description'] = desc
        results.append(result)
    
    with open('recipes_with_descriptions.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    # sample_recipe = """
    # "id": "vegetable_dish-鸡蛋花",
    #     "dish_name": "鸡蛋花",
    #     "description": "鸡蛋花是一道简单易做的菜。有着润肺止咳、缓解喉咙不适的家常食疗方。对于初学者，做一遍即可学会。有甜和咸两种做法。",
    #     "difficulty": "★",
    #     "key_ingredients": "每次制作前需要确定计划做几份。一份正好够 1 个人吃。\n\n每份：\n\n- 鸡蛋 1 个 （去壳后约 50 g）\n- 沸水 100 - 150 ml\n- 白糖 5 - 10 g （如制作甜口）\n- 食盐 1 - 2 g （如制作咸口）",
    #     "recipe": "- 将鸡蛋打入碗中。\n- 使用筷子或搅拌器，顺着一个方向搅打蛋液，直至蛋清与蛋黄完全混合均匀，颜色一致。（此过程约需 1 - 2 分钟）\n- 将糖或盐等调味料加入蛋液中，略微搅匀。\n- 准备刚烧开的、100 ℃ 的沸水。\n- **一边用筷子快速搅拌碗中的蛋液，一边将沸水以细流状冲入蛋液中**。确保沸水与蛋液充分混合。\n- 持续搅拌片刻，直至蛋液被完全烫熟，形成均匀的淡黄色蛋花。"
    # """
    # print(generate_description(sample_recipe))
    main()