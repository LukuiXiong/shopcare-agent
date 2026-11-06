"""索引建好后执行：uv run python -m scripts.check_retrieval。"""
from app.rag import search_rules


if __name__ == "__main__":
    # 检查不同订单类型能否把正确规则排在第一位
    cases = [
        ("普通现货付款后多久发货", "SHIP-001"),
        ("预售订单没有承诺发货时间能判断超时吗", "SHIP-002"),
        ("定制订单按什么时间发货", "SHIP-003"),
        ("已经发货如何判断曾经延迟", "SHIP-004"),
        ("催发货登记成功需要什么凭据", "SHIP-005"),
    ]
    for query, expected in cases:
        results = search_rules(query)["results"]
        assert results and results[0]["rule_id"] == expected, (query, results)
        assert results[0]["source"] == "knowledge/shipping_rules.md"
        print(f"通过：{query} → {expected}")
