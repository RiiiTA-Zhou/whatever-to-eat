"""
LLM-as-Judge 推荐质量评估脚本

使用独立的 LLM 对 agent 回复进行多维度打分。

流程:
1. 为每个测试场景创建模拟用户（写入 users_history）
2. 调用 agent.chat() 获取推荐回复
3. 将用户上下文 + 查询 + agent 回复发送给 judge LLM
4. Judge LLM 按 6 个维度打分
5. 汇总并输出评估报告

用法:
    python evaluation/eval_llm_judge.py
    python evaluation/eval_llm_judge.py --scenario rec_001 rec_003  # 只跑指定场景
"""

import json
import sys
import os
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from whatever_agent import RecipeAgent, llm, tools
from user_memory import UserMemoryManager

load_dotenv()

# Judge LLM — 使用 deepseek-v4-pro，temperature=0 保证评分一致性
judge_llm = ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=os.getenv("AGENT_API_KEY"),
    base_url=os.getenv("AGENT_BASE_URL"),
    temperature=0.0,
    timeout=60,
    streaming=False,
)

# =========== 评估 Prompt ===========

JUDGE_PROMPT = """你是一个专业的推荐系统评估专家。请根据以下信息，对菜谱推荐 agent 的回复进行评分。

## 用户信息
- 用户口味偏好: {tastes}
- 用户不喜欢: {dislikes}
- 用户忌口/过敏: {avoid}
- 厨艺难度偏好: {difficulty_pref}（1=小白，5=大厨）
- 近期饮食: {recent_meals}

## 用户查询
{query}

## Agent 回复
{response}

## 评分标准

请按以下 6 个维度打分，每个维度 1-5 分（1=很差，5=完美），并给出简要理由。

1. **相关性** (relevance): 推荐是否直接回应用户查询？是否理解了用户的真实需求？
2. **偏好一致性** (preference_adherence): 推荐是否符合用户的口味偏好？是否避免了用户不喜欢和忌口的食物？
3. **多样性** (diversity): 推荐是否避免了与近期饮食重复？是否保证了饮食多样性？
4. **完整性** (completeness): 是否包含完整的一顿饭（主食+1-3个菜）？是否包含逐步做法？是否荤素搭配？
5. **营养合理性** (nutrition): 推荐搭配是否符合营养学原理？是否健康均衡？
6. **综合评分** (overall): 整体推荐质量，考虑所有因素后的综合判断。

## 输出格式

只输出一个 JSON 对象，不要包含任何其他文字：

{{
    "relevance": <1-5>,
    "relevance_reason": "<一句话理由>",
    "preference_adherence": <1-5>,
    "preference_reason": "<一句话理由>",
    "diversity": <1-5>,
    "diversity_reason": "<一句话理由>",
    "completeness": <1-5>,
    "completeness_reason": "<一句话理由>",
    "nutrition": <1-5>,
    "nutrition_reason": "<一句话理由>",
    "overall": <1-5>,
    "overall_reason": "<一句话理由>"
}}
"""


def load_test_scenarios() -> list[dict]:
    """加载推荐评估测试场景"""
    test_file = Path(__file__).parent / "test_cases.json"
    with open(test_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["recommendation"]["scenarios"]


def setup_test_user(scenario: dict):
    """为测试场景创建用户记忆文件"""
    user_id = scenario["user_id"]
    memory_path = Path(f"./users_history/{user_id}.json")

    setup = scenario["setup"]
    prefs = setup["preferences"]
    recent = setup.get("recent_meals", [])

    memory_data = {
        "user_id": user_id,
        "preferences": {
            "tastes": prefs.get("tastes", []),
            "dislikes": prefs.get("dislikes", []),
            "avoid": prefs.get("avoid", []),
            "difficulty_preference": prefs.get("difficulty_preference")
        },
        "recent_meals": [
            {"date": m["date"], "dish": m["dish"]}
            for m in recent
        ]
    }

    os.makedirs(memory_path.parent, exist_ok=True)
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=2)


def call_judge(scenario: dict, response: str) -> dict:
    """调用 judge LLM 对回复评分"""
    setup = scenario["setup"]
    prefs = setup["preferences"]
    recent_meals = setup.get("recent_meals", [])

    recent_text = "\n".join(
        f"  - {m['date']}: {m['dish']}" for m in recent_meals
    ) if recent_meals else "（无近期记录）"

    prompt = JUDGE_PROMPT.format(
        tastes=", ".join(prefs.get("tastes", [])) or "（未设置）",
        dislikes=", ".join(prefs.get("dislikes", [])) or "（未设置）",
        avoid=", ".join(prefs.get("avoid", [])) or "（无）",
        difficulty_pref=prefs.get("difficulty_preference") or "（未设置）",
        recent_meals=recent_text,
        query=scenario["query"],
        response=response
    )

    try:
        result = judge_llm.invoke(prompt)
        text = result.content.strip()

        # Parse JSON — handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[-1].split("```")[0].strip()

        scores = json.loads(text)
        return scores

    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON 解析失败: {e}")
        print(f"  Raw response: {text[:200]}...")
        return {
            "relevance": -1, "relevance_reason": "parse_error",
            "preference_adherence": -1, "preference_reason": "parse_error",
            "diversity": -1, "diversity_reason": "parse_error",
            "completeness": -1, "completeness_reason": "parse_error",
            "nutrition": -1, "nutrition_reason": "parse_error",
            "overall": -1, "overall_reason": "parse_error"
        }
    except Exception as e:
        print(f"  [ERROR] Judge 调用失败: {e}")
        return None


def run_llm_judge_eval(scenarios: list[dict], verbose: bool = True) -> dict:
    """运行 LLM-as-Judge 评估"""

    results = []
    dimension_scores = {
        "relevance": [],
        "preference_adherence": [],
        "diversity": [],
        "completeness": [],
        "nutrition": [],
        "overall": []
    }

    for i, scenario in enumerate(scenarios):
        sid = scenario["id"]
        user_id = scenario["user_id"]
        query = scenario["query"]

        if verbose:
            print(f"\n[{i+1}/{len(scenarios)}] {sid}: {scenario['name']}")
            print(f"  用户: {user_id} | 查询: {query}")

        # 1. Setup user
        setup_test_user(scenario)

        # 2. Clear agent cache for this user so it reloads memory
        from api import agent_cache
        if user_id in agent_cache:
            del agent_cache[user_id]

        # 3. Create agent and get response
        try:
            agent = RecipeAgent(user_id=user_id, llm=llm, tools=tools)
            response = agent.chat(query)
        except Exception as e:
            print(f"  [ERROR] Agent 调用失败: {e}")
            results.append({
                "scenario_id": sid,
                "name": scenario["name"],
                "user_id": user_id,
                "query": query,
                "response": f"ERROR: {e}",
                "scores": None,
                "error": str(e)
            })
            continue

        if verbose:
            # Truncate response for display, strip non-ASCII for Windows console
            display = response[:150].replace("\n", " ") + "..." if len(response) > 150 else response.replace("\n", " ")
            display = display.encode("gbk", errors="replace").decode("gbk", errors="replace")
            print(f"  回复: {display}")

        # 4. Judge
        if verbose:
            print(f"  评分中...")
        scores = call_judge(scenario, response)

        if scores is None:
            results.append({
                "scenario_id": sid,
                "name": scenario["name"],
                "user_id": user_id,
                "query": query,
                "response": response,
                "scores": None,
                "error": "judge_failed"
            })
            continue

        # 5. Collect
        for dim in dimension_scores:
            if dim in scores and scores[dim] >= 0:
                dimension_scores[dim].append(scores[dim])

        result_entry = {
            "scenario_id": sid,
            "name": scenario["name"],
            "user_id": user_id,
            "query": query,
            "response": response,
            "scores": scores
        }
        results.append(result_entry)

        if verbose:
            print(f"  评分: overall={scores.get('overall', '?')}, "
                  f"relevance={scores.get('relevance', '?')}, "
                  f"preference={scores.get('preference_adherence', '?')}, "
                  f"diversity={scores.get('diversity', '?')}, "
                  f"completeness={scores.get('completeness', '?')}, "
                  f"nutrition={scores.get('nutrition', '?')}")

        # Brief pause to avoid rate limits
        time.sleep(0.5)

    # Aggregate
    summary = {}
    for dim, vals in dimension_scores.items():
        if vals:
            summary[dim] = {
                "mean": round(sum(vals) / len(vals), 2),
                "min": min(vals),
                "max": max(vals),
                "count": len(vals)
            }
        else:
            summary[dim] = {"mean": 0, "min": 0, "max": 0, "count": 0}

    return {
        "timestamp": datetime.now().isoformat(),
        "total_scenarios": len(scenarios),
        "completed": len([r for r in results if r["scores"] is not None]),
        "errors": len([r for r in results if "error" in r]),
        "summary": summary,
        "results": results
    }


def print_report(eval_results: dict):
    """打印评估报告"""
    summary = eval_results["summary"]

    print("\n" + "=" * 60)
    print("  LLM-as-Judge 推荐质量评估报告")
    print("=" * 60)
    print(f"  评估时间:     {eval_results['timestamp']}")
    print(f"  总场景数:     {eval_results['total_scenarios']}")
    print(f"  成功完成:     {eval_results['completed']}")
    print(f"  失败:         {eval_results['errors']}")
    print("-" * 60)
    print(f"  {'维度':<20} {'均分':<8} {'最低':<8} {'最高':<8} {'样本数':<8}")
    print("  " + "-" * 46)

    dim_labels = {
        "relevance": "相关性",
        "preference_adherence": "偏好一致性",
        "diversity": "多样性",
        "completeness": "完整性",
        "nutrition": "营养合理性",
        "overall": "综合评分"
    }

    for dim, label in dim_labels.items():
        if dim in summary:
            s = summary[dim]
            print(f"  {label:<20} {s['mean']:<8.2f} {s['min']:<8} {s['max']:<8} {s['count']:<8}")

    print("-" * 60)
    if summary.get("overall", {}).get("mean", 0) > 0:
        overall_mean = summary["overall"]["mean"]
        print(f"  >>> 综合均分: {overall_mean:.2f} / 5.00")

    # Per-scenario results
    print("\n  --- 各场景详情 ---")
    for r in eval_results["results"]:
        scores = r.get("scores")
        if scores:
            print(f"  [{r['scenario_id']}] {r['name']}")
            print(f"    整体: {scores.get('overall','?')} | "
                  f"相关: {scores.get('relevance','?')} | "
                  f"偏好: {scores.get('preference_adherence','?')} | "
                  f"多样: {scores.get('diversity','?')} | "
                  f"完整: {scores.get('completeness','?')} | "
                  f"营养: {scores.get('nutrition','?')}")
        else:
            print(f"  [{r['scenario_id']}] {r['name']} — ERROR: {r.get('error')}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="LLM-as-Judge 推荐质量评估")
    parser.add_argument("--scenario", nargs="*", default=None,
                        help="只运行指定场景 ID (如: rec_001 rec_003)")
    parser.add_argument("--quiet", action="store_true",
                        help="减少输出")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅加载场景不实际调用 agent")
    args = parser.parse_args()

    print("加载测试场景...")
    all_scenarios = load_test_scenarios()
    print(f"共 {len(all_scenarios)} 个测试场景")

    if args.scenario:
        scenarios = [s for s in all_scenarios if s["id"] in args.scenario]
        if not scenarios:
            print(f"未找到指定场景: {args.scenario}")
            print(f"可用场景: {[s['id'] for s in all_scenarios]}")
            return
        print(f"筛选后: {len(scenarios)} 个场景")
    else:
        scenarios = all_scenarios

    if args.dry_run:
        print("\n[Dry Run] 场景列表:")
        for s in scenarios:
            print(f"  {s['id']}: {s['name']} (用户: {s['user_id']})")
            print(f"    查询: {s['query']}")
            print(f"    偏好: {s['setup']['preferences']}")
            print(f"    近期饮食: {len(s['setup'].get('recent_meals', []))} 条")
            print()
        return

    print("\n开始评估 (这将调用 LLM，可能需要几分钟)...")
    results = run_llm_judge_eval(scenarios, verbose=not args.quiet)
    print_report(results)

    # Save results
    output_file = Path(__file__).parent / "judge_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存至: {output_file}")

    # Save readable report
    report_file = Path(__file__).parent / "judge_report.md"
    _save_markdown_report(results, report_file)
    print(f"可读报告已保存至: {report_file}")


def _save_markdown_report(results: dict, filepath: Path):
    """保存 Markdown 格式的评估报告"""
    summary = results["summary"]

    lines = [
        "# LLM-as-Judge 推荐质量评估报告",
        "",
        f"- 评估时间: {results['timestamp']}",
        f"- 总场景数: {results['total_scenarios']}",
        f"- 成功: {results['completed']} | 失败: {results['errors']}",
        "",
        "## 综合评分",
        "",
        "| 维度 | 均分 | 最低 | 最高 |",
        "|------|------|------|------|",
    ]

    dim_labels = [
        ("relevance", "相关性"),
        ("preference_adherence", "偏好一致性"),
        ("diversity", "多样性"),
        ("completeness", "完整性"),
        ("nutrition", "营养合理性"),
        ("overall", "综合评分"),
    ]

    for dim, label in dim_labels:
        if dim in summary and summary[dim]["count"] > 0:
            s = summary[dim]
            lines.append(f"| {label} | {s['mean']:.2f} | {s['min']} | {s['max']} |")

    lines.append("")
    lines.append("## 各场景详情")
    lines.append("")

    for r in results["results"]:
        scores = r.get("scores")
        if scores:
            lines.append(f"### {r['scenario_id']}: {r['name']}")
            lines.append(f"")
            lines.append(f"- **查询**: {r['query']}")
            lines.append(f"- **整体评分**: {scores.get('overall', '?')}")
            lines.append(f"- 相关性: {scores.get('relevance', '?')} — {scores.get('relevance_reason', '')}")
            lines.append(f"- 偏好一致性: {scores.get('preference_adherence', '?')} — {scores.get('preference_reason', '')}")
            lines.append(f"- 多样性: {scores.get('diversity', '?')} — {scores.get('diversity_reason', '')}")
            lines.append(f"- 完整性: {scores.get('completeness', '?')} — {scores.get('completeness_reason', '')}")
            lines.append(f"- 营养合理性: {scores.get('nutrition', '?')} — {scores.get('nutrition_reason', '')}")
            lines.append(f"")
            lines.append(f"<details>")
            lines.append(f"<summary>Agent 完整回复</summary>")
            lines.append(f"")
            lines.append(f"```")
            lines.append(r['response'][:2000])
            lines.append(f"```")
            lines.append(f"</details>")
            lines.append(f"")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
