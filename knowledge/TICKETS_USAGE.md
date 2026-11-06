# 本地模拟催发货工单

数据库：data/shopcare.sqlite3，数据库不提交版本库。
服务：http://127.0.0.1:8002/docs，POST /chat。

## 调用链

用户明确要求登记 → Agent 查询订单和规则 → MCP create_shipping_reminder(order_id)
→ 重新通过 Time MCP 获取时间并核验超时 → 仅限已超时且待发货 → SQLite 登记
→ 返回真实工单编号、状态和是否新建 → 模型回答。

同一订单存在 open 状态的催发货工单时返回原工单，唯一索引防止并发重复登记。
时间获取失败、订单不存在、未超时、已发货、数据不足均不会创建工单。
工单类型 shipping_reminder 表示催发货，open 表示待处理。
支持 close_shipping_reminder(ticket_id, close_note="用户要求关闭")：本轮明确要求关闭时调用，通过 Time MCP 记录 closed_at，保存 close_note，状态改为 closed（已关闭）。
重复关闭返回首次关闭记录，不覆盖时间或备注；编号不存在或取时失败不关闭。旧表在写入事务中增加字段，保留数据，只读查询不修改数据库。
关闭后若订单仍超时且待发货，用户再次明确要求登记时可以新建工单。关闭不会修改订单、不会联系真实商家，也不代表问题已解决。
验证：uv run python -m scripts.check_ticket_close（使用临时数据库）。

## 查询工单

已接入 get_shipping_reminder(order_id)：按订单号返回所有本地催发货工单，按创建时间倒序。
调用链：聊天查询 → LangGraph → MCP 查询工具 → SQLite 只读连接 → 返回编号、状态、创建时间。
数据库或工单表尚未创建时返回空列表，不初始化存储；查询失败单独返回失败，不冒充无工单。
可发送“查询 ORD1002 的催发货进度”，open 必须显示为待处理，不代表商家正在处理。

```powershell
# 验证只读、无工单、异常及跨进程查询
uv run python -m scripts.check_ticket_query
```

## 测试

```powershell
# 使用临时数据库验证条件、重复、并发及跨进程持久化，不污染业务库
uv run python -m scripts.check_tickets
```

聊天示例：
- “ORD1002 是否超时？”：只查询，不应创建。
- “ORD1002 超时的话帮我登记催发货”：创建或返回原工单。
- “帮 ORD1004 登记催发货”：预售缺少时间，不登记。

仅询问是否超时不创建的约束由 Agent 提示词执行；工具自身强制核验订单条件，当前尚无独立的用户授权状态管理。
