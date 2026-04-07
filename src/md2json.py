import os
import json
import re

def parse_md(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'!\[.+?\]\(.+?\)', '', content).strip()

    # 解析标题
    title_match = re.search(r'# (.+?)的做法', content)
    dish_name = title_match.group(1) if title_match else ''

    # 描述：从标题后到预估烹饪难度前
    desc_match = re.search(r'# .+?的做法\n\n(.+?)\n\n预估烹饪难度', content, re.DOTALL)
    description = desc_match.group(1).strip() if desc_match else ''

    # 难度
    diff_match = re.search(r'预估烹饪难度：(.+?)\n', content)
    difficulty = diff_match.group(1).strip() if diff_match else ''

    # 计算：## 计算 后的内容直到下一个##
    calc_match = re.search(r'## 计算\s+(.+?)\s+## 操作', content, re.DOTALL)
    key_ingredients = calc_match.group(1).strip() if calc_match else ''

    # 操作：## 操作 和 ## 附加内容 之间的内容
    recipe_match = re.search(r'## 操作\s+(.+?)\s+## 附加内容', content, re.DOTALL)
    recipe = recipe_match.group(1).strip() if recipe_match else ''

    # 附加内容：## 附加内容 到最终提示语之间的内容
    additional_match = re.search(
        r'## 附加内容\s+(.+?)\s+如果您遵循本指南的制作流程而发现有问题或可以改进的流程，请提出 Issue 或 Pull request。',
        content,
        re.DOTALL
    )
    additional = additional_match.group(1).strip() if additional_match else ''

    # 将附加内容拼接到description
    if additional:
        description = description.rstrip() + '\n\n' + additional.rstrip()

    # id: 子文件夹-菜名
    # file_path like data/dishes/aquatic/水煮鱼.md 或 data/dishes/aquatic/小龙虾/小龙虾.md
    parts = file_path.replace('\\', '/').split('/')
    dishes_idx = parts.index('dishes')
    subfolder = parts[dishes_idx + 1]
    id_value = f"{subfolder}-{dish_name}"

    return {
        'id': id_value,
        'dish_name': dish_name,
        'description': description,
        'difficulty': difficulty,
        'key_ingredients': key_ingredients,
        'recipe': recipe
    }

def main():
    base_dir = 'data/dishes'
    recipes = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.md'):
                file_path = os.path.join(root, file)
                recipe = parse_md(file_path)
                recipes.append(recipe)

    with open('recipes.json', 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=4)

if __name__ == '__main__':
    main()