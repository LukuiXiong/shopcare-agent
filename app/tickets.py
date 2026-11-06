"""SQLite 本地模拟工单，不会向商家发送通知。"""
import sqlite3
from pathlib import Path
from uuid import uuid4

DB_PATH = Path(__file__).resolve().parent.parent / "data/shopcare.sqlite3"


def prepare_ticket_schema(connection):
    """在写入事务中兼容旧表，保留现有工单。"""
    connection.execute("""CREATE TABLE IF NOT EXISTS tickets (
        ticket_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
        type TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)""")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(tickets)")}
    for name in ("closed_at", "close_note"):
        if name not in columns:
            connection.execute(f"ALTER TABLE tickets ADD COLUMN {name} TEXT")
    connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS unique_open_reminder
        ON tickets(order_id, type) WHERE status = 'open'""")


def close_shipping_ticket(ticket_id, closed_at, close_note, db_path=DB_PATH):
    """按工单编号原子关闭；重复关闭保留第一次的时间和备注。"""
    path = Path(db_path).resolve()
    if not path.exists():
        return {"success": False, "closed": False, "message": "未找到该工单"}
    connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            # 提前获取写锁，避免并发迁移及重复关闭覆盖首次记录。
            connection.execute("BEGIN IMMEDIATE")
            prepare_ticket_schema(connection)
            row = connection.execute(
                "SELECT * FROM tickets WHERE ticket_id=? AND type='shipping_reminder'",
                (ticket_id.strip(),),
            ).fetchone()
            if row is None:
                return {"success": False, "closed": False, "message": "未找到该工单"}
            if row["status"] == "closed":
                return {"success": True, "closed": False, "ticket": dict(row), "message": "工单已关闭，返回原记录"}
            if row["status"] != "open":
                return {"success": False, "closed": False, "message": "当前状态不支持关闭"}
            connection.execute(
                "UPDATE tickets SET status='closed', closed_at=?, close_note=? WHERE ticket_id=? AND status='open'",
                (closed_at, close_note.strip(), ticket_id.strip()),
            )
            ticket = dict(connection.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id.strip(),)).fetchone())
        return {"success": True, "closed": True, "ticket": ticket, "message": "本地模拟工单已关闭"}
    finally:
        connection.close()


def find_shipping_reminders(order_id, db_path=DB_PATH):
    """只读查询所有催发货工单，查询不会创建数据库、表或工单。"""
    order_id = order_id.strip().upper()
    path = Path(db_path).resolve()
    if not path.exists():
        return []
    # mode=ro 强制只读；参数绑定避免把用户输入当作 SQL 执行
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tickets'"
        ).fetchone()
        if table is None:
            return []
        rows = connection.execute(
            "SELECT * FROM tickets WHERE order_id = ? AND type = 'shipping_reminder' "
            "ORDER BY created_at DESC, ticket_id DESC", (order_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def save_shipping_reminder(order_id, created_at, db_path=DB_PATH):
    # 路径仅由程序配置，模型不能指定数据库位置
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            prepare_ticket_schema(connection)
        with connection:
            ticket_id = "SHIP-" + uuid4().hex
            cursor = connection.execute(
                "INSERT OR IGNORE INTO tickets (ticket_id,order_id,type,status,created_at) VALUES (?, ?, 'shipping_reminder', 'open', ?)",
                (ticket_id, order_id, created_at),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                "SELECT * FROM tickets WHERE order_id = ? AND type = 'shipping_reminder' AND status = 'open'",
                (order_id,),
            ).fetchone()
        return {"success": True, "created": created, "ticket": dict(row),
                "message": "本地模拟工单登记成功" if created else "已有未完成的本地模拟工单，返回原工单"}
    finally:
        connection.close()
