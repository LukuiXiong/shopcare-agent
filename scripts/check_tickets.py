"""运行：uv run python -m scripts.check_tickets；使用临时数据库，不污染演示数据。"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
import subprocess
import sys

from app.tickets import save_shipping_reminder
import mcp_server


async def check(db):
    async def fixed_time():
        return "2026-11-05T12:00:00+08:00"

    saver = partial(save_shipping_reminder, db_path=db)
    with patch.object(mcp_server, "read_current_time", fixed_time), patch("app.tickets.save_shipping_reminder", saver):
        first = await mcp_server.create_shipping_reminder(" ord1002 ")
        again = await mcp_server.create_shipping_reminder("ORD1002")
        assert first["success"] and first["created"]
        assert again["success"] and not again["created"]
        assert first["ticket"] == again["ticket"]
        for order_id in ("ORD1001", "ORD1003", "ORD1004", "ORD9999"):
            assert not (await mcp_server.create_shipping_reminder(order_id))["success"]

    async def broken_time():
        raise RuntimeError("模拟取时故障")

    with patch.object(mcp_server, "read_current_time", broken_time), patch("app.tickets.save_shipping_reminder", saver):
        assert not (await mcp_server.create_shipping_reminder("ORD1005"))["success"]


if __name__ == "__main__":
    with TemporaryDirectory() as folder:
        db = Path(folder) / "tickets.sqlite3"
        asyncio.run(check(db))
        # 并发创建同一订单，数据库中只允许一条未完成工单
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: save_shipping_reminder("ORD1005", "2026-11-05T12:00:00+08:00", db), range(8)))
        assert sum(r["created"] for r in results) == 1
        with closing(sqlite3.connect(db)) as connection:
            assert connection.execute("SELECT count(*) FROM tickets").fetchone()[0] == 2
        # 新 Python 进程读取同一数据库，验证跨进程持久化和防重复
        code = "from app.tickets import save_shipping_reminder; import sys; r=save_shipping_reminder('ORD1002','2026-11-05T12:00:00+08:00',sys.argv[1]); assert r['success'] and not r['created']"
        subprocess.run([sys.executable, "-c", code, str(db)], check=True)
    print("工单条件、防重复、并发、取时失败和跨进程持久化检查通过")
