"""验证只读查询：uv run python -m scripts.check_ticket_query。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import sqlite3
import subprocess
import sys

from app.tickets import find_shipping_reminders, save_shipping_reminder
import mcp_server


if __name__ == "__main__":
    with TemporaryDirectory() as folder:
        db = Path(folder) / "tickets.sqlite3"
        assert find_shipping_reminders("ORD1002", db) == []
        assert not db.exists()  # 查询不能创建数据库
        with sqlite3.connect(db) as connection:
            connection.execute("CREATE TABLE unrelated (id INTEGER)")
        connection.close()
        assert find_shipping_reminders("ORD1002", db) == []
        saved = save_shipping_reminder("ORD1002", "2026-11-05T12:00:00+08:00", db)
        before = db.read_bytes()
        rows = find_shipping_reminders(" ord1002 ", db)
        assert rows == [saved["ticket"]]
        assert rows[0]["status"] == "open"
        assert find_shipping_reminders("ORD9999", db) == []
        assert find_shipping_reminders("' OR 1=1 --", db) == []
        assert db.read_bytes() == before  # 已有数据库同样不能被写入
        # 新进程模拟服务重启，仍返回原工单编号
        code = "from app.tickets import find_shipping_reminders; import sys; assert find_shipping_reminders('ORD1002',sys.argv[1])[0]['ticket_id']==sys.argv[2]"
        subprocess.run([sys.executable, "-c", code, str(db), saved["ticket"]["ticket_id"]], check=True)
        with patch("app.tickets.find_shipping_reminders", side_effect=sqlite3.OperationalError):
            assert mcp_server.get_shipping_reminder("ORD1002")["success"] is False
    print("只读查询、无工单、输入规范化、SQL 输入、跨进程持久化和故障检查通过")
