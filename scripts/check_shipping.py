"""固定时间验证边界：uv run python -m scripts.check_shipping。"""
from app.orders import MOCK_ORDERS, evaluate_shipping


if __name__ == "__main__":
    cases = [
        ("ORD1002", "2026-11-03T09:59:59+08:00", "未超时"),
        ("ORD1002", "2026-11-03T10:00:00+08:00", "未超时"),
        ("ORD1002", "2026-11-03T10:00:01+08:00", "已超时"),
        ("ORD1002", "2026-11-03T02:00:00+00:00", "未超时"),
        ("ORD1003", "2026-11-05T10:00:00+08:00", "未超时"),
        ("ORD1004", "2026-11-05T10:00:00+08:00", "信息不足"),
        ("ORD1005", "2026-11-05T10:00:00+08:00", "已超时"),
        ("ORD1001", "2026-11-05T10:00:00+08:00", "未超时"),
        ("ORD1002", "2026-11-05T10:00:00", "信息不足"),
    ]
    for order_id, now, expected in cases:
        result = evaluate_shipping(MOCK_ORDERS[order_id], now)
        assert result["result"] == expected, result
    # 明确承诺时间优先于付款后 48 小时；已发货按实际发货时间判断
    changed = {**MOCK_ORDERS["ORD1002"], "promised_ship_at": "2026-12-01T10:00:00+08:00"}
    assert evaluate_shipping(changed, "2026-11-05T10:00:00+08:00")["result"] == "未超时"
    changed = {**MOCK_ORDERS["ORD1001"], "shipped_at": "2026-11-03T10:00:01+08:00"}
    assert evaluate_shipping(changed, "2026-11-05T10:00:00+08:00")["result"] == "已超时"
    print("全部 11 项时间判断检查通过")
