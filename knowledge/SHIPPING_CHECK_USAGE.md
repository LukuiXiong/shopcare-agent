# 发货超时判断

接口：http://127.0.0.1:8002/docs，POST /chat。

## 文件及链路

- app/orders.py：模拟订单、带时区的日期解析及纯 Python 判断。
- mcp_server.py：提供 check_shipping_overdue(order_id)；内部以 stdio 启动 mcp-server-time，调用 get_current_time(Asia/Shanghai)，完成后关闭短会话和子进程。模型不能传入当前时间。
- app/agent.py：要求查询订单、检索规则并调用判断工具，引用时间和规则来源。

链路：用户 → FastAPI → LangGraph → 订单/规则 MCP → check_shipping_overdue → Time MCP → Python 比较时间 → 模型组织回答。

Time MCP 使用本机系统时钟，不是独立网络授时服务；应保持系统时间准确。
规则检索用于说明依据，计算按 demo-v1 确定执行；修改规则时须同步修改 app/orders.py 和重建 RAG 索引。
已接入本地模拟工单，详见 TICKETS_USAGE.md；不会通知真实商家。

## 演示订单

| 订单 | 场景 |
|---|---|
| ORD1001 | 普通现货，已在截止前发货 |
| ORD1002 | 普通现货，2026-11-03 10:00 截止，仍待发货 |
| ORD1003 | 预售，2026-12-01 10:00 截止 |
| ORD1004 | 预售，缺少承诺时间，信息不足 |
| ORD1005 | 定制，2026-11-04 10:00 截止 |

## 验证

```powershell
# 使用固定时间验证边界，不依赖当天日期
uv run python -m scripts.check_shipping
# 服务未运行时启动；修改代码后需重启
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

当前时间等于截止时间时未超时；已发货订单比较实际发货时间。
Time MCP 获取失败时返回信息不足，不使用本地替代时间，也不使用模型猜测时间。
