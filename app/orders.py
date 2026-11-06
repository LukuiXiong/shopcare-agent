"""模拟订单和纯 Python 时间判断；固定时间仅由测试代码传入。"""
from datetime import datetime, timedelta

# 所有日期明确带北京时间偏移；None 表示数据缺失，不由模型补齐
MOCK_ORDERS = {
    "ORD1001": dict(order_id="ORD1001", product="无线鼠标", status="已发货",
        order_type="普通现货", paid_at="2026-11-01T10:00:00+08:00",
        promised_ship_at=None, shipped_at="2026-11-03T09:00:00+08:00"),
    "ORD1002": dict(order_id="ORD1002", product="机械键盘", status="待发货",
        order_type="普通现货", paid_at="2026-11-01T10:00:00+08:00",
        promised_ship_at=None, shipped_at=None),
    "ORD1003": dict(order_id="ORD1003", product="预售耳机", status="待发货",
        order_type="预售", paid_at="2026-11-01T10:00:00+08:00",
        promised_ship_at="2026-12-01T10:00:00+08:00", shipped_at=None),
    "ORD1004": dict(order_id="ORD1004", product="预售音箱", status="待发货",
        order_type="预售", paid_at="2026-11-01T10:00:00+08:00",
        promised_ship_at=None, shipped_at=None),
    "ORD1005": dict(order_id="ORD1005", product="定制桌", status="待发货",
        order_type="定制", paid_at="2026-11-01T10:00:00+08:00",
        promised_ship_at="2026-11-04T10:00:00+08:00", shipped_at=None),
}


def parse_time(value):
    # 拒绝无时区时间，防止系统时区不同导致比较错误
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return parsed


def evaluate_shipping(order, current_time):
    """按 demo-v1 规则计算，规则文档变更时应同步修改本函数。"""
    result = {"source": "模拟订单数据", "order_id": order["order_id"],
              "checked_at": current_time, "rule_version": "demo-v1",
              "rule_source": "knowledge/shipping_rules.md", "result": "信息不足"}
    rule = {"普通现货": "SHIP-001", "预售": "SHIP-002", "定制": "SHIP-003"}
    result["rule_id"] = rule.get(order.get("order_type"))
    try:
        now = parse_time(current_time)
        if result["rule_id"] is None:
            raise ValueError("缺少有效订单类型")
        deadline_text = order.get("promised_ship_at")
        if deadline_text:
            deadline = parse_time(deadline_text)
        elif order["order_type"] == "普通现货" and order.get("paid_at"):
            deadline = parse_time(order["paid_at"]) + timedelta(hours=48)
        else:
            raise ValueError("缺少付款时间或承诺/约定发货截止时间")
        result["deadline"] = deadline.isoformat()
        if order["status"] == "已发货":
            if not order.get("shipped_at"):
                raise ValueError("已发货订单缺少实际发货时间")
            compared = parse_time(order["shipped_at"])
            if compared > now:
                raise ValueError("实际发货时间晚于当前时间，订单数据异常")
            result["comparison_basis"] = "实际发货时间"
        elif order["status"] == "待发货":
            compared = now
            result["comparison_basis"] = "Time MCP 当前时间"
        else:
            raise ValueError("不支持的订单状态")
        result.update(result="已超时" if compared > deadline else "未超时",
                      compared_at=compared.isoformat(),
                      overdue_seconds=max(0, (compared - deadline).total_seconds()))
    except (ValueError, TypeError) as exc:
        result["reason"] = str(exc)
    return result
