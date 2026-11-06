import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP
from app.rag import get_store, search_rules

# stdio 的标准输出专用于协议，查询日志写入标准错误
mcp = FastMCP("shopcare-orders")

# 用字典模拟订单数据库，本阶段不连接真实订单系统
from app.orders import MOCK_ORDERS, evaluate_shipping


# 将查询函数发布为 MCP 工具
@mcp.tool()
def get_order(order_id: str) -> dict:
    """根据订单号查询模拟订单信息，例如 ORD1002。"""
    # 去掉首尾空格并转成大写，兼容 ord1002 这样的输入
    order_id = order_id.strip().upper()

    # 在模拟数据库中查找订单
    order = MOCK_ORDERS.get(order_id)

    # 终端打印查询记录，方便确认模型确实调用了工具
    print(f"[MCP 订单工具] 查询订单：{order_id}", file=sys.stderr)

    if order is None:
        return {
            "source": "模拟订单数据",
            "found": False,
            "order_id": order_id,
            "message": "未找到该订单",
        }

    return {
        "source": "模拟订单数据",
        "found": True,
        "order": order,
    }

@mcp.tool()
def search_shipping_rules(query: str) -> dict:
    """检索 ShopCare 模拟发货规则，返回规则内容、编号和来源。"""
    # 模型在服务启动时加载一次；日志必须写 stderr
    print(f"[MCP 规则检索] {query}", file=sys.stderr)
    return search_rules(query)


async def read_current_time():
    # 通过真正的 Time MCP 子进程获取时间；不允许模型传入或覆盖当前时间
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server_time", "--local-timezone=Asia/Shanghai"],
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            response = await session.call_tool(
                "get_current_time", {"timezone": "Asia/Shanghai"},
            )
            if response.isError:
                raise ValueError("Time MCP 返回错误")
            data = json.loads(next(c.text for c in response.content if c.type == "text"))
            if data["timezone"] != "Asia/Shanghai":
                raise ValueError("Time MCP 返回了非预期时区")
            return data["datetime"]


@mcp.tool()
async def check_shipping_overdue(order_id: str) -> dict:
    """判断模拟订单是否超过发货时限，自动从 Time MCP 获取北京时间，无需传入当前时间。"""
    import asyncio
    order_id = order_id.strip().upper()
    print(f"[MCP 超时判断] {order_id}", file=sys.stderr)
    order = MOCK_ORDERS.get(order_id)
    if order is None:
        return {"order_id": order_id, "result": "信息不足", "reason": "未找到模拟订单"}
    try:
        # 每次判断打开短会话，结束或超时会自动关闭 Time MCP 子进程
        current_time = await asyncio.wait_for(read_current_time(), timeout=20)
    except Exception:
        return {"order_id": order_id, "result": "信息不足",
                "reason": "Time MCP 获取时间失败，无法完成判断"}
    result = evaluate_shipping(order, current_time)
    result["time_source"] = "Time MCP / get_current_time / Asia/Shanghai"
    return result


@mcp.tool()
async def create_shipping_reminder(order_id: str) -> dict:
    """仅在用户明确要求登记催发货时调用；重新核验模拟订单超时情况，保存本地工单并防重复。"""
    from app.tickets import save_shipping_reminder
    order_id = order_id.strip().upper()
    print(f"[MCP 工单登记] {order_id}", file=sys.stderr)
    # 创建前重新获取时间并核验，不能接受模型传入的超时结论
    check = await check_shipping_overdue(order_id)
    order = MOCK_ORDERS.get(order_id)
    if order is None or order["status"] != "待发货" or check["result"] != "已超时":
        return {"success": False, "created": False, "check": check,
                "message": "未登记：仅对已超时且待发货的模拟订单创建工单"}
    try:
        result = save_shipping_reminder(order_id, check["checked_at"])
    except Exception:
        return {"success": False, "created": False, "message": "本地工单保存失败，请稍后重试"}
    result["check"] = check
    result["notice"] = "仅登记本地模拟工单，未通知商家"
    return result


@mcp.tool()
def get_shipping_reminder(order_id: str) -> dict:
    """根据订单号只读查询本地催发货工单，返回编号、状态和创建时间；不会登记新工单。"""
    from app.tickets import find_shipping_reminders
    order_id = order_id.strip().upper()
    print(f"[MCP 工单查询] {order_id}", file=sys.stderr)
    try:
        tickets = find_shipping_reminders(order_id)
    except Exception:
        return {"success": False, "order_id": order_id,
                "message": "工单查询失败，请稍后重试"}
    return {"success": True, "found": bool(tickets), "order_id": order_id,
            "tickets": tickets, "status_labels": {"open": "待处理", "closed": "已关闭"},
            "message": "查询成功" if tickets else "该订单没有本地催发货工单",
            "notice": "仅本地模拟工单，open 表示待处理，不代表商家收到或正在处理"}


@mcp.tool()
async def close_shipping_reminder(ticket_id: str, close_note: str = "用户要求关闭") -> dict:
    """仅在本轮用户明确要求关闭指定编号工单时调用。备注使用用户原话，未提供则用默认值；不会修改订单或通知商家。"""
    import asyncio
    from app.tickets import close_shipping_ticket
    ticket_id, close_note = ticket_id.strip(), close_note.strip()
    if not ticket_id or len(ticket_id) > 100 or not close_note or len(close_note) > 500:
        return {"success": False, "closed": False, "message": "工单编号不能为空且最多100字，关闭备注需为1～500字"}
    try:
        closed_at = await asyncio.wait_for(read_current_time(), timeout=20)
    except Exception:
        return {"success": False, "closed": False, "message": "Time MCP 获取时间失败，未关闭工单"}
    try:
        result = close_shipping_ticket(ticket_id, closed_at, close_note)
    except Exception:
        return {"success": False, "closed": False, "message": "关闭操作失败，请先查询工单确认状态"}
    result["notice"] = "仅关闭本地模拟工单，不代表商家处理完毕或订单已发货"
    return result


if __name__ == "__main__":
    # 在主线程预热模型，避免首次请求在工具工作线程中执行重型导入
    get_store()
    # 由 FastAPI 的 MCP Client 启动，通过标准输入输出通信
    mcp.run(transport="stdio")
