"""
检索质量评估脚本

评估 RAG 管道的语义检索质量，计算 Hit Rate @k、MRR、NDCG @k。

用法:
    python evaluation/eval_retrieval.py
    python evaluation/eval_retrieval.py --k 5
"""

import json
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recipe_retrieval_tool import load_vector_store
import numpy as np


def load_test_cases() -> list[dict]:
    """加载检索测试用例"""
    test_file = Path(__file__).parent / "test_cases.json"
    with open(test_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["retrieval"]["test_queries"]


def run_retrieval_eval(vector_store, test_cases: list[dict], k: int = 3) -> dict:
    """运行检索评估并计算指标"""

    hit_count = 0
    reciprocal_ranks = []
    dcg_scores = []
    idcg_scores = []
    details = []

    for case in test_cases:
        query = case["query"]
        expected = case["expected_ids"]

        # Run search directly against vector store to get structured results
        results = vector_store.similarity_search_with_score(query=query, k=k)

        # Extract recipe IDs from returned documents
        returned_ids = []
        for doc, score in results:
            # doc.metadata contains the recipe metadata; check for dish_name or id
            doc_id = doc.metadata.get("id", "") or doc.metadata.get("dish_name", "")
            returned_ids.append(doc_id)

        # Calculate metrics for this query
        # Hit Rate: does any expected ID appear in returned IDs?
        hit = any(eid in returned_ids for eid in expected)
        if hit:
            hit_count += 1

        # Reciprocal Rank (MRR): rank of first relevant result
        rr = 0.0
        for rank, rid in enumerate(returned_ids, 1):
            if rid in expected:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # NDCG: relevance = 1 if in expected set, 0 otherwise
        relevances = [1.0 if rid in expected else 0.0 for rid in returned_ids]

        # DCG @k
        dcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(relevances))

        # IDCG @k (ideal: all relevant first)
        ideal_rels = sorted(relevances, reverse=True)
        idcg = sum(rel / np.log2(i + 2) for i, rel in enumerate(ideal_rels))

        dcg_scores.append(dcg)
        idcg_scores.append(idcg)

        details.append({
            "query": query,
            "expected_ids": expected,
            "returned_ids": returned_ids,
            "hit": hit,
            "rr": round(rr, 4),
            "dcg": round(dcg, 4),
            "idcg": round(idcg, 4)
        })

    n = len(test_cases)

    # Aggregate metrics
    hit_rate = hit_count / n
    mrr = np.mean(reciprocal_ranks)
    ndcg = np.mean([d / i if i > 0 else 0.0 for d, i in zip(dcg_scores, idcg_scores)])

    return {
        "total_queries": n,
        "k": k,
        "hit_rate@k": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "ndcg@k": round(ndcg, 4),
        "details": details
    }


def print_results(results: dict):
    """打印评估结果"""
    print("=" * 60)
    print(f"  检索质量评估报告 (k={results['k']})")
    print("=" * 60)
    print(f"  测试查询数:  {results['total_queries']}")
    print(f"  Hit Rate @{results['k']}: {results['hit_rate@k']:.2%}  ({results['hit_rate@k']*results['total_queries']:.0f}/{results['total_queries']})")
    print(f"  MRR:          {results['mrr']:.4f}")
    print(f"  NDCG @{results['k']}:      {results['ndcg@k']:.4f}")
    print("-" * 60)

    # Per-category breakdown
    categories = {}
    for d in results["details"]:
        cat = "other"
        for case in load_test_cases():
            if case["query"] == d["query"]:
                cat = case["category"]
                break
        if cat not in categories:
            categories[cat] = {"hits": 0, "total": 0, "rr_sum": 0}
        categories[cat]["total"] += 1
        if d["hit"]:
            categories[cat]["hits"] += 1
        categories[cat]["rr_sum"] += d["rr"]

    print("\n  按类别分组:")
    print(f"  {'类别':<22} {'数量':<6} {'Hit Rate':<10} {'MRR':<8}")
    print("  " + "-" * 46)
    for cat, stats in sorted(categories.items()):
        cat_hr = stats["hits"] / stats["total"]
        cat_mrr = stats["rr_sum"] / stats["total"]
        print(f"  {cat:<22} {stats['total']:<6} {cat_hr:<10.2%} {cat_mrr:<8.4f}")

    # Print failed queries
    failed = [d for d in results["details"] if not d["hit"]]
    if failed:
        print("\n  [MISS] 未命中查询:")
        for d in failed:
            print(f"    查询: {d['query']}")
            print(f"    期望: {d['expected_ids']}")
            print(f"    返回: {d['returned_ids']}")
            print()

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="检索质量评估")
    parser.add_argument("--k", type=int, default=3, help="Top-k 检索数量 (默认: 3)")
    args = parser.parse_args()

    print("加载向量数据库...")
    vector_store = load_vector_store()

    print("加载测试用例...")
    test_cases = load_test_cases()
    print(f"共 {len(test_cases)} 条测试查询\n")

    results = run_retrieval_eval(vector_store, test_cases, k=args.k)
    print_results(results)

    # Save detailed results
    output_file = Path(__file__).parent / "retrieval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存至: {output_file}")


if __name__ == "__main__":
    main()
