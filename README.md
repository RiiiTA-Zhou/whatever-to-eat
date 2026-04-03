# 随便：今天吃什么

不知道今天吃什么？随便Agent来给你建议。

## 核心功能

- 外卖/堂食模式：根据地理位置和口味偏好推荐吃的给你
- 做饭模式：根据你的做饭水平推荐菜谱给你
- 记忆模块：记住你的口味偏好等信息，还记住最近你吃了什么，保证你不吃腻
- 保证营养：根据你近期饮食状况给你推荐更营养的美食

## Workflow
1. 解析用户输入（Input Normalization）
- 将用户的自然语言输入（例如“今天想吃什么/不吃辣/想外卖”）通过 LangChain 提示词改写成严格符合 `schemas/UserInput.json` 的 JSON。
- 如缺少必填字段（例如当 `mode` 为 `delivery` 或 `dine_in` 时需要 `location`），进入追问循环：先补齐字段，再继续。

2. 加载本地记忆（Memory Loading）
- 从本地记忆存储中读取：
  - 长期偏好：喜欢/不喜欢的口味、忌口、做饭能力等
  - 近期历史：最近吃了什么（用于“不重复”）
- 将近期历史按 `history_window` 口径拼入 prompt（或作为 `history_entries` 注入）。

3. 按模式构建候选与任务（Mode Branching）
- `mode = delivery`：外卖模式
  - 使用 `location` + 口味偏好/忌口形成筛选条件
  - （可选）调用外部 API 或本地候选池，得到“店铺/菜品候选”
  - 生成主推荐与 2-3 个备选，并给出为什么推荐
- `mode = dine_in`：堂食模式
  - 同外卖模式，但把“到达时间”替换为“就餐时长/到达时长”的口径
  - 主推荐与备选都输出成严格 JSON
- `mode = cook`：做饭模式
  - 根据 `cooking_skill` 与口味偏好筛选候选菜谱（可来自你仓库内的菜谱数据；若没有数据，可先让 LLM 生成菜谱雏形再二次结构化）
  - 生成菜谱名、关键步骤、食材清单、预计用时、替代建议、营养标签

4. 策略打分与去重（Scoring & Dedup）
- 将历史“不重复”做成硬/软约束（例如：最近 N 天/最近 N 次出现过的同类菜，降低分数）
- 结合偏好与忌口做一致性校验（硬性过滤 + 软性重排）
- 让最终排序结果影响：
  - 主推荐的选择
  - 备选的多样性（避免备选和主推荐过于相似）

5. 生成最终输出（Strict JSON Output）
- 让 LangChain 输出严格符合 `schemas/Output.json` 的 JSON：
  - `mode`
  - `main_recommendation`（按对应模式选择结构）
  - `alternatives`（2-3 个备选）
  - `response`（自然语言解释 + 推荐原因）
- 用结构化输出解析器（PydanticOutputParser 或基于 JSON Schema 的校验器）保证输出可解析、可验证。

6. 更新本地记忆（Memory Update）
- 将本次主推荐（菜品/菜谱名）写入近期历史
- 根据用户的隐含/显式偏好（例如 `liked_flavors`、`disliked_flavors`、`rating_last`）更新长期偏好

