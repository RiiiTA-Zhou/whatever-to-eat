2026.4.7

embedding做好了

./src/recipe_retrieval_tool.py: 从向量库里检索

返回结果：results = [(Document, score)]

Doc = (id, metadata, page_content)

./src/we_search_tool.py: 用DDG检索，返回结果：[{title, url, content}]

用户偏好记忆：

```
user_profile = {
    "user_id": "user_123",
    "preferences": {
        "tastes": ["麻辣", "鲜香", "酸辣"],      # 喜欢的口味
        "dislikes": ["甜口", "太油腻"],          # 不喜欢
        "avoid": ["花生", "海鲜"],           # 过敏食材等忌口
        "difficulty_preference": 2              # 偏好难度（1-3）
    },
    "recent_meals": [                         # 近期饮食记录
        {"date": "2024-01-15", "dish": "麻辣香锅", "meal": "晚餐"},
        {"date": "2024-01-14", "dish": "番茄炒蛋", "meal": "午餐"},
        {"date": "2024-01-13", "dish": "宫保鸡丁", "meal": "晚餐"}
    ]
}
```

tools:
self.tool_definitions = [
            {
                "name": "search_recipes",
                "description": "从本地菜谱数据库中搜索相关菜谱",
                "parameters": {
                    "query": "搜索查询，如'清淡的鸡肉菜'，或'辣椒炒肉'"
                }
            },
            {
                "name": "search_recipes_with_filters",
                "description": "从本地菜谱数据库中搜索相关菜谱，支持难度，菜名关键词，关键材料等过滤条件",
                "parameters": {
                    "query": "搜索查询，如'清淡的鸡肉菜'，或'辣椒炒肉'",
                    "difficulty": "难度级别，1-5 数值，表示菜谱的难易程度",
                    "key_ingredients": "关键材料列表，如['鸡肉', '辣椒']"
                }
            },
            {
                "name": "web_search",
                "description": "通过网络搜索获取外部菜谱信息或餐厅信息",
                "parameters": {
                    "query": "搜索查询，如'猪肺汤 菜谱'，或'香辣 螃蟹 菜谱'"
                }
            },
            {
                "name": "meal_planning",
                "description": "根据搜索结果和用户信息生成最终推荐的整套菜单，包含多个菜谱",
                "parameters": {
                    "people": "用餐人数，用于确定菜量",
                    "query": "用户对于菜谱的额外要求"
                }
            }
        ]

2026.4.6

洗好之后想要用llm生成description和key_ingredient

最终数据：./data/recipes.json


2026.4.5

决定直接用howtocook就好了，然后想用正则表达式洗成json

2026.4.3

尝试清洗数据。

收集到的数据：entities_item.json：来自[CookBook-KG](https://github.com/ngl567/CookBook-KG)

[HowToCook](https://github.com/Anduin2017/HowToCook)

顺便有一个MCP服务：
https://github.com/DusKing1/howtocook-py-mcp


2026.4.2

重新来一遍，手工为主，不要急

今天实现了llm调用，预计先做做饭模式。实现了多轮对话。

接下来要把菜谱接入到知识库中。然后就是实现记忆功能。
