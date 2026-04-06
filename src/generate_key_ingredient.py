prompt = \
'''你是一个美食专家，专门为用户提供菜品的关键食材。请根据提供的菜谱，提取并列出该菜品所需的关键食材，不重要的调味料（如盐、胡椒粉、糖、油等）可以省略，且只列出食材名称，不需要数量和其他描述信息。请将提取的关键食材以逗号分隔的形式输出，且不要添加任何额外的文字说明。

{recipe}'''


import json

from utils import OpenAIModel, LLMConfig
from dotenv import load_dotenv
import os
from tqdm import tqdm

load_dotenv()

dpsk = LLMConfig(api_key=os.getenv("LLM_API_KEY"), llm_name=os.getenv("LLM_MODEL_ID"), base_url=os.getenv("LLM_BASE_URL"))
llm = OpenAIModel(dpsk)

def generate_key_ingredients(recipe):
    prompt_with_recipe = prompt.format(recipe=recipe)
    key_ingredients = llm.generate(prompt_with_recipe)
    return key_ingredients.strip()

def main():
    with open('recipes_with_descriptions.json', 'r', encoding='utf-8') as f:
        recipes = json.load(f)
    
    results = []
    for recipe in tqdm(recipes, desc="Generating key ingredients"):
        key_ingredients = generate_key_ingredients(recipe['recipe'])
        result = recipe.copy()
        result['ingreditent_list'] = recipe['key_ingredients']
        result['key_ingredients'] = key_ingredients
        results.append(result)
    
    with open('recipes_with_key_ingredients.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    # sample_recipe = """
    # {
    #     "id": "meat_dish-带把肘子",
    #     "dish_name": "带把肘子",
    #     "description": "这道菜属于荤菜，口味咸香浓郁，肉质酥烂脱骨。肘子经煮、蒸多道工序，外皮红亮，入口即化，适合作为宴客主菜或家庭聚餐的硬菜，搭配葱段与甜面酱食用风味更佳。",
    #     "difficulty": "★★★★★",
    #     "key_ingredients": "每份：三人量\n\n- 带脚、爪猪前肘: 一个（大约二斤五两 = 1250 克）\n- 红豆腐乳: 1 块 = 10 克\n- 甜面酱: 150 克\n- 精盐: 15 克\n- 红酱油: 35 克\n- 白酱油: 25 克\n- 料酒: 25 克\n- 蒜片: 50 克\n- 姜末: 10 克\n- 八角: 3 个\n- 桂皮: 5 克\n- 葱: 200 克",
    #     "recipe": "- 将肘子刮洗干净，肘头朝外、肘把（脚爪）朝里、肘皮朝下放在案板上。\n- 用刀在正中由肘头向肘把沿着腿骨将皮剖开，剔去腿骨两边的肉（三面离肉），底部骨与肉相连，使骨头露出，然后将两节腿骨由中间用刀背（还是用斧头吧）砸断。\n- 肘子放入煮锅煮至七成熟捞出（外观正常，内部淡红色），用干净抹布擦干水，趁热用红酱油涂抹肉皮。\n- 取蒸锅一个，锅底放入八角、桂皮，先将肘把的关节处用手掰断，不伤外皮，再将肘皮朝下装进蒸锅内，装锅时根据肘子体型，将肘把贴住锅边窝着装进锅内，成为圆形。\n- 撒入精盐，用消过毒的干净纱布盖在肉上，再将甜面酱（50 克）、葱（75 克）、红豆腐乳、红酱油、白酱油、姜、蒜等在纱布上抹开，用旺火蒸大约三小时（以蒸烂为准）。\n- 蒸完取出，揭去纱布，扣入盘中，拣去八角，上桌时另带葱段和甜面酱小碟（或将甜面酱抹到肘面上，另带葱段小碟亦可）。"
    # }
    # """
    # print(generate_key_ingredients(sample_recipe))
    main()